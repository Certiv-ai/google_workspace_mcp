"""
New forward_gmail_message tool to add to gmail_tools.py

Add this function after the batch_modify_gmail_message_labels function.
Also add these imports at the top:
- from email.mime.multipart import MIMEMultipart
- from email.mime.base import MIMEBase
- from email import encoders
"""

@server.tool()
@handle_http_errors("forward_gmail_message", service_type="gmail")
@require_google_service("gmail", GMAIL_SEND_SCOPE)
async def forward_gmail_message(
    service,
    user_google_email: str,
    message_id: str = Body(..., description="The ID of the message to forward"),
    to: str = Body(..., description="Recipient email address"),
) -> str:
    """
    Forward a Gmail message with all attachments preserved.

    This tool downloads the original message including all attachments
    and forwards it to the specified recipient. Unlike send_gmail_message,
    this preserves PDF receipts and other attachments that are critical
    for expense tracking and documentation.

    Args:
        user_google_email (str): The user's Google email address. Required.
        message_id (str): The ID of the Gmail message to forward
        to (str): Recipient email address

    Returns:
        str: Confirmation message with the forwarded email's message ID

    Example:
        forward_gmail_message(
            message_id="19c496d7dc2d9298",
            to="receipts@expensify.com"
        )
    """
    logger.info(
        f"[forward_gmail_message] Invoked. Email: '{user_google_email}', Message ID: '{message_id}', To: '{to}'"
    )

    # Get the original message with full content
    original_msg = await asyncio.to_thread(
        service.users().messages().get(userId="me", id=message_id, format="full").execute
    )

    payload = original_msg.get("payload", {})
    headers = payload.get("headers", [])

    # Extract original subject
    original_subject = next(
        (h["value"] for h in headers if h["name"] == "Subject"),
        "No Subject"
    )

    # Create multipart message
    forward_msg = MIMEMultipart()
    forward_msg["To"] = to
    forward_msg["Subject"] = f"Fwd: {original_subject}"
    forward_msg["From"] = user_google_email

    # Extract and add body content
    bodies = _extract_message_bodies(payload)
    text_body = bodies.get("text", "")
    html_body = bodies.get("html", "")

    if html_body:
        forward_msg.attach(MIMEText(html_body, "html"))
    elif text_body:
        forward_msg.attach(MIMEText(text_body, "plain"))
    else:
        forward_msg.attach(MIMEText("[No body content]", "plain"))

    # Extract and download attachments
    attachments = _extract_attachments(payload)
    attachment_count = 0

    if attachments:
        logger.info(f"[forward_gmail_message] Found {len(attachments)} attachments to forward")

        for att in attachments:
            try:
                # Download attachment content
                attachment_data = await asyncio.to_thread(
                    service.users()
                    .messages()
                    .attachments()
                    .get(userId="me", messageId=message_id, id=att["attachmentId"])
                    .execute
                )

                # Decode base64 content
                file_data = base64.urlsafe_b64decode(attachment_data.get("data", ""))

                # Create MIME attachment part
                mime_part = MIMEBase("application", "octet-stream")
                mime_part.set_payload(file_data)
                encoders.encode_base64(mime_part)
                mime_part.add_header(
                    "Content-Disposition",
                    f'attachment; filename="{att["filename"]}"'
                )
                mime_part.set_type(att.get("mimeType", "application/octet-stream"))

                forward_msg.attach(mime_part)
                attachment_count += 1

                logger.info(
                    f"[forward_gmail_message] Attached: {att['filename']} ({att['size']} bytes)"
                )

            except Exception as e:
                logger.error(
                    f"[forward_gmail_message] Failed to attach {att['filename']}: {e}"
                )
                # Continue with other attachments even if one fails

    # Encode and send the forward message
    raw_message = base64.urlsafe_b64encode(forward_msg.as_bytes()).decode("utf-8")
    send_body = {"raw": raw_message}

    sent_message = await asyncio.to_thread(
        service.users().messages().send(userId="me", body=send_body).execute
    )

    message_id = sent_message.get("id")

    result = f"Email forwarded successfully!\nMessage ID: {message_id}"
    if attachment_count > 0:
        result += f"\nAttachments forwarded: {attachment_count}"

    logger.info(f"[forward_gmail_message] Successfully forwarded with {attachment_count} attachments")

    return result
