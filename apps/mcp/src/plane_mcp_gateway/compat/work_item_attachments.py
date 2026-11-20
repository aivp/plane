"""保留附件的旧返回类型，下载和上传均交给 v0.3.6 的资源处理器。"""

from typing import Any

from fastmcp.utilities.types import Image
from plane_mcp.tools import workitem_attachment

from plane_mcp_gateway.compat.resources import resource_handler

workitem_attachment_action = resource_handler(workitem_attachment)


def list_work_item_attachments(
    project_id: str,
    work_item_id: str,
) -> list[dict[str, Any]]:
    """
    List all attachments for a work item.

    Returns metadata for each attachment. To get a downloadable link
    for a specific attachment, use get_work_item_attachment_download_url.

    Args:
        project_id: UUID of the project
        work_item_id: UUID of the work item

    Returns:
        List of attachments, each with: id, name, size, content_type,
        created_at, created_by.
    """
    # 旧入口将上游附件元数据序列化为数组。
    return workitem_attachment_action(
        "list", project_id=project_id, workitem_id=work_item_id
    )


def get_work_item_attachment_download_url(
    project_id: str,
    work_item_id: str,
    attachment_id: str,
) -> dict[str, Any]:
    """
    Get a presigned download URL for a work item attachment.

    Returns a time-limited URL (typically valid ~1 hour) that can be
    opened directly in a browser or downloaded with any HTTP client —
    no Plane authentication required on the URL itself.

    Use list_work_item_attachments first to get attachment IDs and names.

    Args:
        project_id: UUID of the project
        work_item_id: UUID of the work item
        attachment_id: UUID of the attachment

    Returns:
        Dict with: download_url (presigned S3 URL), attachment_id, name.
    """
    # 在上游查询附件签名链接，保留原有字段。
    return workitem_attachment_action(
        "download_url",
        project_id=project_id,
        workitem_id=work_item_id,
        attachment_id=attachment_id,
    )


def upload_work_item_attachment_from_url(
    project_id: str,
    work_item_id: str,
    url: str,
    name: str | None = None,
) -> dict[str, Any]:
    """
    Fetch a file from a public URL and attach it to a work item.

    The MCP server downloads the file server-side and uploads it to Plane
    via the standard three-step presigned S3 flow. The source URL must be
    publicly accessible without authentication and must not resolve to a
    private/internal network address.

    Args:
        project_id: UUID of the project
        work_item_id: UUID of the work item
        url: Publicly accessible URL of the file to attach
            (e.g. a GitHub raw URL, public S3 link, or direct download link)
        name: Override the filename. Defaults to the filename in the URL path.

    Returns:
        Created attachment metadata: id, name, size, content_type.
    """
    # 由 v0.3.6 校验来源并下载，将可选文件名转为上游缺省值。
    return workitem_attachment_action(
        "upload_from_url",
        project_id=project_id,
        workitem_id=work_item_id,
        url=url,
        name=name or "",
    )


def delete_work_item_attachment(
    project_id: str,
    work_item_id: str,
    attachment_id: str,
) -> None:
    """
    Delete an attachment from a work item.

    Use list_work_item_attachments to get the attachment_id.

    Args:
        project_id: UUID of the project
        work_item_id: UUID of the work item
        attachment_id: UUID of the attachment to delete
    """
    # 固定删除操作，通用资源的其他动作不对调用方开放。
    workitem_attachment_action(
        "delete",
        project_id=project_id,
        workitem_id=work_item_id,
        attachment_id=attachment_id,
    )


def read_work_item_attachment(
    project_id: str,
    work_item_id: str,
    attachment_id: str,
) -> Image | str:
    """
    Fetch an attachment's content so the LLM can read or analyze it.

    Supported file types:
      Images (returned as vision-readable image, max 5 MB):
        PNG, JPEG, GIF, WEBP
      Text (returned as a string, max 1 MB):
        TXT, MD, CSV, HTML, XML, YAML, JSON

    Not supported (use get_work_item_attachment_download_url instead):
      PDF            — requires a text-extraction library (not installed)
      DOCX/XLSX/PPTX — binary Office formats, require extraction
      Audio / Video  — non-textual binary formats
      Generic binary — executables, archives, etc.

    Args:
        project_id: UUID of the project
        work_item_id: UUID of the work item
        attachment_id: UUID of the attachment

    Returns:
        Image object for image files, plain string for text files.

    Raises:
        ValueError: If the file type is unsupported or the file exceeds
                    the size limit for its category.
    """
    # 保留二进制图片与文本两种 MCP 内容类型。
    return workitem_attachment_action(
        "read",
        project_id=project_id,
        workitem_id=work_item_id,
        attachment_id=attachment_id,
    )
