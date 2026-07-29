# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Safe PQL subset compiler for the external work-item API.

Plane's public MCP server sends PQL to the work-item list endpoint, while the
Community API does not ship the Pro PQL engine. This module intentionally
implements a small, allowlisted compatibility subset. Unsupported syntax fails
closed instead of being ignored.
"""

import ast
import calendar
import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

from django.db.models import Q
from django.utils import timezone


MAX_PQL_LENGTH = 2_000
MAX_PQL_CONDITIONS = 5
MAX_IN_VALUES = 100

OPEN_STATE_GROUPS = ("backlog", "unstarted", "started")
CLOSED_STATE_GROUPS = ("completed", "cancelled")
ACTIVE_STATE_GROUPS = ("unstarted", "started")

PRIORITIES = {"urgent", "high", "medium", "low", "none"}
STATE_GROUPS = set(OPEN_STATE_GROUPS + CLOSED_STATE_GROUPS)


class PQLParseError(ValueError):
    """Raised when a PQL expression is invalid or outside the supported subset."""


@dataclass(frozen=True)
class _Token:
    kind: str
    value: str
    position: int


@dataclass(frozen=True)
class _FieldSpec:
    lookup: str
    value_type: str
    active_lookup: str | None = None


_FIELD_SPECS = {
    "priority": _FieldSpec("priority", "priority"),
    "stategroup": _FieldSpec("state__group", "state_group"),
    "title": _FieldSpec("name", "text"),
    "duedate": _FieldSpec("target_date", "date"),
    "startdate": _FieldSpec("start_date", "date"),
    "createdat": _FieldSpec("created_at", "datetime"),
    "updatedat": _FieldSpec("updated_at", "datetime"),
    "assignee": _FieldSpec(
        "issue_assignee__assignee_id",
        "uuid",
        "issue_assignee__deleted_at__isnull",
    ),
    "state": _FieldSpec("state_id", "uuid"),
    "label": _FieldSpec(
        "label_issue__label_id",
        "uuid",
        "label_issue__deleted_at__isnull",
    ),
    "cycle": _FieldSpec(
        "issue_cycle__cycle_id",
        "uuid",
        "issue_cycle__deleted_at__isnull",
    ),
    "module": _FieldSpec(
        "issue_module__module_id",
        "uuid",
        "issue_module__deleted_at__isnull",
    ),
    "project": _FieldSpec("project_id", "uuid"),
    "createdby": _FieldSpec("created_by_id", "uuid"),
    "type": _FieldSpec("type_id", "uuid"),
    "mention": _FieldSpec(
        "issue_mention__mention_id",
        "uuid",
        "issue_mention__deleted_at__isnull",
    ),
    "subscriber": _FieldSpec(
        "issue_subscribers__subscriber_id",
        "uuid",
        "issue_subscribers__deleted_at__isnull",
    ),
}

_TOKEN_RE = re.compile(
    r"""
    (?P<SPACE>\s+)
    |(?P<STRING>"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')
    |(?P<NUMBER>-?\d+(?:\.\d+)?)
    |(?P<OP>!=|>=|<=|=|>|<|~)
    |(?P<LPAREN>\()
    |(?P<RPAREN>\))
    |(?P<COMMA>,)
    |(?P<IDENT>[A-Za-z_][A-Za-z0-9_]*)
    |(?P<MISMATCH>.)
    """,
    re.VERBOSE,
)


def _tokenize(query: str) -> list[_Token]:
    tokens: list[_Token] = []
    for match in _TOKEN_RE.finditer(query):
        kind = match.lastgroup
        value = match.group()
        if kind == "SPACE":
            continue
        if kind == "MISMATCH":
            raise PQLParseError(f"Unexpected character {value!r} at position {match.start()}.")
        tokens.append(_Token(kind=kind or "", value=value, position=match.start()))
    tokens.append(_Token(kind="EOF", value="", position=len(query)))
    return tokens


class _PQLParser:
    def __init__(self, query: str, user_id: str):
        self.tokens = _tokenize(query)
        self.index = 0
        self.user_id = str(user_id)
        self.condition_count = 0

    @property
    def current(self) -> _Token:
        return self.tokens[self.index]

    def parse(self) -> Q:
        result = self._parse_or()
        if self.current.kind != "EOF":
            raise self._error(f"Unexpected token {self.current.value!r}.")
        return result

    def _parse_or(self) -> Q:
        result = self._parse_and()
        while self._match_keyword("OR"):
            result |= self._parse_and()
        return result

    def _parse_and(self) -> Q:
        result = self._parse_not()
        while self._match_keyword("AND"):
            result &= self._parse_not()
        return result

    def _parse_not(self) -> Q:
        if self._match_keyword("NOT"):
            return ~self._parse_not()
        return self._parse_primary()

    def _parse_primary(self) -> Q:
        if self._match_kind("LPAREN"):
            result = self._parse_or()
            self._expect_kind("RPAREN")
            return result
        return self._parse_condition()

    def _parse_condition(self) -> Q:
        name = self._expect_kind("IDENT").value
        if self.current.kind == "LPAREN":
            args = self._parse_function_args()
            self._record_condition()
            return self._compile_predicate(name, args)

        operator = self._parse_operator()
        self._record_condition()

        if operator in {"IS NULL", "IS NOT NULL", "IS EMPTY", "IS NOT EMPTY"}:
            return self._compile_field(name, operator, None)

        if operator in {"IN", "NOT IN"}:
            value = self._parse_in_value()
            return self._compile_field(name, operator, value)

        if operator == "BETWEEN":
            value = self._parse_between_value()
            return self._compile_field(name, operator, value)

        return self._compile_field(name, operator, self._parse_value())

    def _parse_operator(self) -> str:
        if self.current.kind == "OP":
            return self._advance().value
        if self._match_keyword("IN"):
            return "IN"
        if self._match_keyword("NOT"):
            self._expect_keyword("IN")
            return "NOT IN"
        if self._match_keyword("IS"):
            is_not = self._match_keyword("NOT")
            if self._match_keyword("NULL"):
                return "IS NOT NULL" if is_not else "IS NULL"
            if self._match_keyword("EMPTY"):
                return "IS NOT EMPTY" if is_not else "IS EMPTY"
            raise self._error("Expected NULL or EMPTY after IS.")
        if self._match_keyword("BETWEEN"):
            return "BETWEEN"
        raise self._error("Expected a PQL comparison operator.")

    def _parse_in_value(self) -> list[Any]:
        if self.current.kind == "IDENT" and self._peek().kind == "LPAREN":
            value = self._parse_value()
            if not isinstance(value, (list, tuple)):
                raise self._error("The function after IN must return a list.")
            return list(value)

        self._expect_kind("LPAREN")
        values: list[Any] = []
        if self.current.kind != "RPAREN":
            values.append(self._parse_value())
            while self._match_kind("COMMA"):
                values.append(self._parse_value())
        self._expect_kind("RPAREN")
        if not values:
            raise self._error("IN requires at least one value.")
        if len(values) > MAX_IN_VALUES:
            raise self._error(f"IN accepts at most {MAX_IN_VALUES} values.")
        return values

    def _parse_between_value(self) -> tuple[Any, Any]:
        if self._match_kind("LPAREN"):
            lower = self._parse_value()
            self._expect_kind("COMMA")
            upper = self._parse_value()
            self._expect_kind("RPAREN")
            return lower, upper

        lower = self._parse_value()
        self._expect_keyword("AND")
        return lower, self._parse_value()

    def _parse_value(self) -> Any:
        token = self.current
        if token.kind == "STRING":
            self._advance()
            try:
                value = ast.literal_eval(token.value)
            except (SyntaxError, ValueError) as exc:
                raise self._error("Invalid quoted string.") from exc
            if not isinstance(value, str):
                raise self._error("PQL quoted values must be strings.")
            return value
        if token.kind == "NUMBER":
            self._advance()
            return float(token.value) if "." in token.value else int(token.value)
        if token.kind == "IDENT":
            name = self._advance().value
            if self.current.kind == "LPAREN":
                args = self._parse_function_args()
                return self._resolve_value_function(name, args)
            if name.lower() == "true":
                return True
            if name.lower() == "false":
                return False
            raise self._error(f"Bare value {name!r} is not supported; quote string values.")
        raise self._error("Expected a PQL value.")

    def _parse_function_args(self) -> list[Any]:
        self._expect_kind("LPAREN")
        args: list[Any] = []
        if self.current.kind != "RPAREN":
            args.append(self._parse_value())
            while self._match_kind("COMMA"):
                args.append(self._parse_value())
        self._expect_kind("RPAREN")
        return args

    def _resolve_value_function(self, name: str, args: list[Any]) -> Any:
        function_name = name.lower()
        if function_name == "currentuser":
            self._require_arg_count(name, args, 0)
            return self.user_id
        if function_name == "openstates":
            self._require_arg_count(name, args, 0)
            return OPEN_STATE_GROUPS
        if function_name == "closedstates":
            self._require_arg_count(name, args, 0)
            return CLOSED_STATE_GROUPS
        if function_name == "activestates":
            self._require_arg_count(name, args, 0)
            return ACTIVE_STATE_GROUPS
        return self._resolve_date_function(name, args)

    def _resolve_date_function(self, name: str, args: list[Any]) -> date | datetime:
        function_name = name.lower()
        now = timezone.now()
        today = timezone.localdate()

        no_arg_values: dict[str, date | datetime] = {
            "today": today,
            "now": now,
            "startofday": timezone.make_aware(datetime.combine(today, time.min)),
            "endofday": timezone.make_aware(datetime.combine(today, time.max)),
            "startofweek": today - timedelta(days=today.weekday()),
            "endofweek": today + timedelta(days=6 - today.weekday()),
            "startofmonth": today.replace(day=1),
            "endofmonth": today.replace(day=calendar.monthrange(today.year, today.month)[1]),
            "startofyear": today.replace(month=1, day=1),
            "endofyear": today.replace(month=12, day=31),
        }
        if function_name in no_arg_values:
            self._require_arg_count(name, args, 0)
            return no_arg_values[function_name]

        relative_functions = {
            "daysago": ("days", -1),
            "daysfromnow": ("days", 1),
            "weeksago": ("weeks", -1),
            "weeksfromnow": ("weeks", 1),
            "monthsago": ("months", -1),
            "monthsfromnow": ("months", 1),
        }
        if function_name not in relative_functions:
            raise self._error(f"Unsupported PQL value function {name}().")

        self._require_arg_count(name, args, 1)
        amount = args[0]
        if not isinstance(amount, int) or amount < 0:
            raise self._error(f"{name}() requires one non-negative integer.")
        unit, direction = relative_functions[function_name]
        if unit == "days":
            return today + timedelta(days=amount * direction)
        if unit == "weeks":
            return today + timedelta(weeks=amount * direction)
        return _shift_months(today, amount * direction)

    def _compile_predicate(self, name: str, args: list[Any]) -> Q:
        function_name = name.lower()
        self._require_arg_count(name, args, 0)

        if function_name == "isoverdue":
            return Q(target_date__lt=timezone.localdate(), state__group__in=OPEN_STATE_GROUPS)
        if function_name == "hasnoassignee":
            return ~Q(issue_assignee__deleted_at__isnull=True)
        if function_name == "hasnolabel":
            return ~Q(label_issue__deleted_at__isnull=True)
        if function_name == "istoplevel":
            return Q(parent__isnull=True)
        if function_name == "issubworkitem":
            return Q(parent__isnull=False)
        if function_name == "haschildren":
            return Q(parent_issue__isnull=False)
        if function_name == "hasstartandduedates":
            return Q(start_date__isnull=False, target_date__isnull=False)
        raise self._error(f"Unsupported PQL predicate {name}().")

    def _compile_field(self, name: str, operator: str, value: Any) -> Q:
        field_name = name.lower()
        if field_name == "text":
            return self._compile_text(operator, value)
        if field_name == "id":
            return self._compile_identifier(operator, value)

        spec = _FIELD_SPECS.get(field_name)
        if spec is None:
            supported = ", ".join(sorted((*_FIELD_SPECS.keys(), "id", "text")))
            raise self._error(f"Unsupported PQL field {name!r}. Supported fields: {supported}.")

        if operator in {"IS NULL", "IS EMPTY", "IS NOT NULL", "IS NOT EMPTY"}:
            return self._compile_null_check(spec, operator)

        if operator == "BETWEEN":
            if spec.value_type not in {"date", "datetime"}:
                raise self._error(f"BETWEEN is not supported for {name}.")
            lower, upper = value
            query = Q(
                **{
                    f"{spec.lookup}__gte": self._normalize_value(spec, lower),
                    f"{spec.lookup}__lte": self._normalize_value(spec, upper),
                }
            )
            return self._with_active_relation(spec, query)

        if operator in {"IN", "NOT IN"}:
            values = [self._normalize_value(spec, item) for item in value]
            query = Q(**{f"{spec.lookup}__in": values})
            query = self._with_active_relation(spec, query)
            return ~query if operator == "NOT IN" else query

        normalized = self._normalize_value(spec, value)
        lookup_suffix = {
            "=": "",
            "!=": "",
            "~": "__icontains",
            ">": "__gt",
            ">=": "__gte",
            "<": "__lt",
            "<=": "__lte",
        }.get(operator)
        if lookup_suffix is None:
            raise self._error(f"Unsupported operator {operator!r}.")
        if operator == "~" and spec.value_type != "text":
            raise self._error(f"The ~ operator is only supported for text fields, not {name}.")
        if operator in {">", ">=", "<", "<="} and spec.value_type not in {"date", "datetime"}:
            raise self._error(f"The {operator} operator is only supported for date fields in this edition.")

        query = Q(**{f"{spec.lookup}{lookup_suffix}": normalized})
        query = self._with_active_relation(spec, query)
        return ~query if operator == "!=" else query

    def _compile_text(self, operator: str, value: Any) -> Q:
        if not isinstance(value, str):
            raise self._error("The text field requires a quoted string.")
        if operator == "~":
            return Q(name__icontains=value) | Q(description_stripped__icontains=value)
        if operator == "=":
            return Q(name=value) | Q(description_stripped=value)
        if operator == "!=":
            return ~(Q(name=value) | Q(description_stripped=value))
        raise self._error("The text field supports only =, !=, and ~.")

    def _compile_identifier(self, operator: str, value: Any) -> Q:
        if not isinstance(value, str):
            raise self._error("The id field requires a quoted identifier or UUID.")
        try:
            issue_id = str(uuid.UUID(value))
        except ValueError:
            issue_id = ""

        if issue_id:
            if operator not in {"=", "!="}:
                raise self._error("A UUID id supports only = and !=.")
            query = Q(id=issue_id)
            return ~query if operator == "!=" else query

        identifier_match = re.fullmatch(r"([A-Za-z0-9_-]+)-(\d+)", value)
        if operator in {"=", "!="} and identifier_match:
            query = Q(
                project__identifier__iexact=identifier_match.group(1),
                sequence_id=int(identifier_match.group(2)),
            )
            return ~query if operator == "!=" else query
        if operator == "~":
            return Q(project__identifier__icontains=value.rstrip("-"))
        raise self._error('id must be a UUID or an identifier such as "WEB-11".')

    def _compile_null_check(self, spec: _FieldSpec, operator: str) -> Q:
        is_null = operator in {"IS NULL", "IS EMPTY"}
        if spec.active_lookup is not None:
            active_relation = Q(**{spec.active_lookup: True})
            return ~active_relation if is_null else active_relation
        query = Q(**{f"{spec.lookup}__isnull": is_null})
        return query

    def _normalize_value(self, spec: _FieldSpec, value: Any) -> Any:
        if spec.value_type == "uuid":
            if not isinstance(value, str):
                raise self._error("UUID fields require a quoted UUID or currentUser().")
            try:
                return str(uuid.UUID(value))
            except ValueError as exc:
                raise self._error(f"Invalid UUID value {value!r}.") from exc
        if spec.value_type == "priority":
            if not isinstance(value, str) or value.lower() not in PRIORITIES:
                raise self._error(f"Priority must be one of: {', '.join(sorted(PRIORITIES))}.")
            return value.lower()
        if spec.value_type == "state_group":
            if not isinstance(value, str) or value.lower() not in STATE_GROUPS:
                raise self._error(f"State group must be one of: {', '.join(sorted(STATE_GROUPS))}.")
            return value.lower()
        if spec.value_type == "text":
            if not isinstance(value, str):
                raise self._error("Text fields require a quoted string.")
            return value
        if spec.value_type in {"date", "datetime"}:
            return self._normalize_date(value)
        return value

    def _normalize_date(self, value: Any) -> date | datetime:
        if isinstance(value, (date, datetime)):
            return value
        if not isinstance(value, str):
            raise self._error("Date fields require an ISO date string or date function.")
        try:
            return datetime.fromisoformat(value) if "T" in value else date.fromisoformat(value)
        except ValueError as exc:
            raise self._error(f"Invalid ISO date value {value!r}.") from exc

    def _with_active_relation(self, spec: _FieldSpec, query: Q) -> Q:
        if spec.active_lookup is None:
            return query
        return query & Q(**{spec.active_lookup: True})

    def _record_condition(self) -> None:
        self.condition_count += 1
        if self.condition_count > MAX_PQL_CONDITIONS:
            raise self._error(f"PQL supports at most {MAX_PQL_CONDITIONS} conditions.")

    def _require_arg_count(self, name: str, args: list[Any], count: int) -> None:
        if len(args) != count:
            raise self._error(f"{name}() expects {count} argument(s).")

    def _peek(self) -> _Token:
        return self.tokens[self.index + 1]

    def _advance(self) -> _Token:
        token = self.current
        self.index += 1
        return token

    def _match_kind(self, kind: str) -> bool:
        if self.current.kind != kind:
            return False
        self._advance()
        return True

    def _expect_kind(self, kind: str) -> _Token:
        if self.current.kind != kind:
            raise self._error(f"Expected {kind}, got {self.current.value!r}.")
        return self._advance()

    def _match_keyword(self, keyword: str) -> bool:
        if self.current.kind != "IDENT" or self.current.value.upper() != keyword:
            return False
        self._advance()
        return True

    def _expect_keyword(self, keyword: str) -> None:
        if not self._match_keyword(keyword):
            raise self._error(f"Expected {keyword}.")

    def _error(self, message: str) -> PQLParseError:
        return PQLParseError(f"{message} (position {self.current.position})")


def _shift_months(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 + months
    year, zero_based_month = divmod(month_index, 12)
    month = zero_based_month + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def compile_work_item_pql(query: str, user_id: str) -> Q:
    """Compile an allowlisted PQL subset into a Django ``Q`` object."""

    normalized_query = query.strip()
    if not normalized_query:
        raise PQLParseError("PQL must not be empty.")
    if len(normalized_query) > MAX_PQL_LENGTH:
        raise PQLParseError(f"PQL must not exceed {MAX_PQL_LENGTH} characters.")
    return _PQLParser(normalized_query, user_id).parse()
