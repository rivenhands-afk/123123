import os
import uuid
import requests
import flet as ft

DEFAULT_API_KEY = "e81d24656b26e877fbcd9755cba9e7da"
NEOCITIES_UPLOAD_URL = "https://neocities.org/api/upload"
NEOCITIES_DELETE_URL = "https://neocities.org/api/delete"
MEDIA_UPLOAD_URL = "https://litterbox.catbox.moe/resources/internals/api.php"
FEED_RAW_URL = "https://cyrillyrikos.neocities.org/feed.txt/feed.txt"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_FEED_FILE = os.path.join(BASE_DIR, "feed.txt")

def main(page: ft.Page):
    page.title = "Neocities Hybrid Uploader"
    page.padding = 15
    page.theme_mode = ft.ThemeMode.DARK
    page.window_width = 620
    page.window_height = 760
    page.window_resizable = False
    page.bgcolor = "#000000"
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER

    api_key_input = ft.TextField(
        label="API KEY",
        value=DEFAULT_API_KEY,
        password=True,
        can_reveal_password=True,
        bgcolor="#0a0a0a",
        color="white",
        border_color="white",
        focused_border_color="white",
        text_size=11,
        border_radius=0,
        label_style=ft.TextStyle(size=10, color="white")
    )

    message_input = ft.TextField(
        multiline=True,
        min_lines=4,
        max_lines=6,
        hint_text="Введите текст поста...",
        hint_style=ft.TextStyle(color="#666666"),
        bgcolor="#0a0a0a",
        color="white",
        border=ft.InputBorder.NONE,
        text_size=13
    )

    attachments_column = ft.Column(spacing=2)
    status_text = ft.Text("Готово к работе", italic=True, color="white", size=11, text_align=ft.TextAlign.CENTER)

    file_picker = ft.FilePicker()
    page.services.append(file_picker)
    selected_files = []

    async def pick_files_click(e):
        nonlocal selected_files
        files = await file_picker.pick_files(allow_multiple=True)
        if files:
            for f in files:
                selected_files.append({
                    "path": f.path,
                    "orig_name": f.name
                })
                attachments_column.controls.append(
                    ft.Text(f"📎 К публикации: {f.name}", size=9, color="#00ffcc")
                )
            status_text.value = f"Выбрано файлов: {len(selected_files)}"
            status_text.color = "white"
            page.update()

    async def process_and_upload(e):
        api_key = api_key_input.value.strip()
        post_content = message_input.value.strip()

        if not api_key:
            status_text.value = "Ошибка: не указан API ключ"
            status_text.color = "#ff4444"
            page.update()
            return

        if not post_content and not selected_files:
            status_text.value = "Ошибка: пустой текст и нет файлов"
            status_text.color = "#ff4444"
            page.update()
            return

        headers = {"Authorization": f"Bearer {api_key}"}
        generated_tags = []

        try:
            if selected_files:
                for item in selected_files:
                    local_path = item["path"]
                    orig_name = item["orig_name"]
                    ext = os.path.splitext(orig_name)[1].lower()

                    # КАРТИНКИ: льем напрямую на Neocities в images/
                    if ext in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
                        status_text.value = f"Загружаю фото {orig_name} на Neocities..."
                        page.update()

                        safe_filename = f"{uuid.uuid4().hex[:8]}{ext}"
                        server_path = f"images/{safe_filename}"

                        with open(local_path, "rb") as f:
                            resp = requests.post(
                                NEOCITIES_UPLOAD_URL,
                                headers=headers,
                                files={server_path: f},
                                timeout=60
                            )

                            if resp.status_code == 200:
                                media_url = f"https://cyrillyrikos.neocities.org/{server_path}"
                                generated_tags.append(f'<img src="{media_url}" alt="">')
                            else:
                                status_text.value = f"Ошибка фото [{resp.status_code}]: {resp.text}"
                                status_text.color = "#ff4444"
                                page.update()
                                return

                    # АУДИО И ВИДЕО: льем на Litterbox (так как они тяжелые и надежнее для медиа)
                    elif ext in (".mp3", ".wav", ".ogg", ".flac", ".mp4", ".webm", ".mov"):
                        status_text.value = f"Загружаю аудио/видео {orig_name} на хостинг..."
                        page.update()

                        with open(local_path, "rb") as f:
                            resp = requests.post(
                                MEDIA_UPLOAD_URL,
                                data={
                                    "reqtype": "fileupload",
                                    "time": "72h"
                                },
                                files={"fileToUpload": (orig_name, f)},
                                timeout=60
                            )

                            if resp.status_code == 200 and resp.text.startswith("http"):
                                media_url = resp.text.strip()
                                if ext in (".mp3", ".wav", ".ogg", ".flac"):
                                    generated_tags.append(f'<audio src="{media_url}" controls></audio>')
                                else:
                                    generated_tags.append(f'<video src="{media_url}" controls style="max-width: 100%;"></video>')
                            else:
                                status_text.value = f"Ошибка хостинга медиа: {resp.text[:80]}"
                                status_text.color = "#ff4444"
                                page.update()
                                return
                    else:
                        # Прочие файлы — на Litterbox с обычной ссылкой
                        with open(local_path, "rb") as f:
                            resp = requests.post(
                                MEDIA_UPLOAD_URL,
                                data={"reqtype": "fileupload", "time": "72h"},
                                files={"fileToUpload": (orig_name, f)},
                                timeout=60
                            )
                            if resp.status_code == 200 and resp.text.startswith("http"):
                                media_url = resp.text.strip()
                                generated_tags.append(f'<a href="{media_url}">{orig_name}</a>')

            if generated_tags:
                media_html_block = "\n".join(generated_tags)
                if post_content:
                    post_content += "\n" + media_html_block
                else:
                    post_content = media_html_block

            # Скачивание текущего фида
            status_text.value = "Синхронизация ленты..."
            page.update()

            existing_feed = ""
            try:
                feed_resp = requests.get(FEED_RAW_URL + "?" + str(uuid.uuid4()), timeout=10)
                if feed_resp.status_code == 200:
                    existing_feed = feed_resp.text
            except Exception:
                pass

            if not existing_feed and os.path.exists(LOCAL_FEED_FILE):
                with open(LOCAL_FEED_FILE, "r", encoding="utf-8") as f:
                    existing_feed = f.read()

            # Сборка нового фида
            updated_feed = f"{post_content}\n\n---\n\n{existing_feed}" if existing_feed.strip() else post_content
            with open(LOCAL_FEED_FILE, "w", encoding="utf-8") as f:
                f.write(updated_feed)

            # Удаление старого feed.txt на Neocities
            status_text.value = "Обновление фида на сервере..."
            page.update()

            requests.post(
                NEOCITIES_DELETE_URL,
                headers=headers,
                data={"filenames[]": "feed.txt"},
                timeout=15
            )

            # Загрузка свежего feed.txt
            with open(LOCAL_FEED_FILE, "rb") as f:
                upload_resp = requests.post(
                    NEOCITIES_UPLOAD_URL,
                    headers=headers,
                    files={"feed.txt": f},
                    timeout=30
                )

                if upload_resp.status_code == 200:
                    status_text.value = "Успешно опубликовано!"
                    status_text.color = "#00ffcc"
                    message_input.value = ""
                    selected_files.clear()
                    attachments_column.controls.clear()
                else:
                    status_text.value = f"Ошибка фида [{upload_resp.status_code}]: {upload_resp.text}"
                    status_text.color = "#ff4444"
        except Exception as ex:
            status_text.value = f"Критический сбой: {str(ex)}"
            status_text.color = "#ff4444"

        page.update()

    page.add(
        ft.Container(
            content=ft.Column([
                ft.Text("Neocities Hybrid Uploader", size=15, weight=ft.FontWeight.BOLD, color="white", text_align=ft.TextAlign.CENTER),
                api_key_input,
                ft.Divider(color="white", height=5),
                ft.Container(
                    content=ft.Column([
                        message_input,
                        attachments_column,
                        ft.Divider(color="#222222", height=1),
                        ft.Row([
                            ft.Button(
                                content="Прикрепить файл", 
                                color="white", 
                                bgcolor="#1a1a1a", 
                                on_click=pick_files_click
                            ),
                            ft.Button(
                                content="Опубликовать", 
                                color="white", 
                                bgcolor="#1a1a1a", 
                                on_click=process_and_upload
                            )
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                    ], spacing=8),
                    bgcolor="#0a0a0a",
                    padding=10
                ),
                ft.Container(
                    content=status_text,
                    alignment="center",
                    padding=5
                )
            ], spacing=8, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=15,
            bgcolor="#000000",
            width=580
        )
    )

if __name__ == "__main__":
    ft.run(main)