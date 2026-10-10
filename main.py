import os
import random
import uuid
import requests
import flet as ft

DEFAULT_API_KEY = "a0bc101a74be2d576125cd64abf6797453d04b51843b538bb90a0a1de43e498e"
DEFAULT_TARGET_DIR = "/cyrillyrikos.nekoweb.org/files"
FEED_REMOTE_PATH = "/cyrillyrikos.nekoweb.org/feed.txt"  # ИСПРАВЛЕНО: теперь файл летит прямо в корень сайта
FEED_RAW_URL = "https://cyrillyrikos.nekoweb.org/feed.txt/feed.txt"  # Ссылка для скачивания актуального фида с сайта
UPLOAD_URL = "https://nekoweb.org/api/files/upload"
DELETE_URL = "https://nekoweb.org/api/files/delete"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_FEED_FILE = os.path.join(BASE_DIR, "feed.txt")

WORDS = [
    "item", "file", "media", "data", "post", "doc", "asset", 
    "archive", "node", "store", "core", "unit", "pack", "batch"
]

def generate_random_name(original_filename):
    ext = os.path.splitext(original_filename)[1]
    word = random.choice(WORDS)
    rand_suffix = uuid.uuid4().hex[:4]
    return f"{word}_{rand_suffix}{ext}"

def main(page: ft.Page):
    page.title = "Nekoweb Uploader & Composer"
    page.padding = 15
    page.theme_mode = ft.ThemeMode.DARK
    page.window_width = 620
    page.window_height = 740
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
    
    target_dir_input = ft.TextField(
        label="Remote Path",
        value=DEFAULT_TARGET_DIR,
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
        hint_text="Введите текст сообщения или поста...",
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
            attachments_column.controls.clear()
            
            for f in files:
                orig_name = f.name
                new_filename = generate_random_name(orig_name)
                
                lower_name = new_filename.lower()
                if lower_name.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
                    tag = f'<img src="f/{new_filename}/{new_filename}" alt="">'
                elif lower_name.endswith((".mp3", ".wav", ".ogg", ".flac")):
                    tag = f'<audio src="f/{new_filename}/{new_filename}" controls style="width: 100%;"></audio>'
                elif lower_name.endswith((".mp4", ".webm", ".mov")):
                    tag = f'<video src="f/{new_filename}/{new_filename}" controls style="max-width: 100%;"></video>'
                else:
                    tag = f'<a href="f/{new_filename}/{new_filename}">{orig_name}</a>'  
                
                selected_files.append({
                    "path": f.path,
                    "orig_name": orig_name,
                    "filename": new_filename,
                    "tag": tag
                })
                
                current_text = message_input.value
                if current_text:
                    message_input.value = current_text + "\n" + tag
                else:
                    message_input.value = tag

                attachments_column.controls.append(
                    ft.Text(f"📎 {orig_name} -> {tag}", size=9, color="#00ffcc")
                )
                
            status_text.value = f"Выбрано файлов: {len(selected_files)}"
            status_text.color = "white"
            page.update()

    def send_message_ritual(e):
        api_key = api_key_input.value.strip()
        target_dir = target_dir_input.value.strip()
        post_content = message_input.value.strip()

        if not api_key:
            status_text.value = "Ошибка: не указан API ключ"
            status_text.color = "#ff4444"
            page.update()
            return

        if not post_content and not selected_files:
            status_text.value = "Ошибка: пустой текст и нет вложений"
            status_text.color = "#ff4444"
            page.update()
            return

        status_text.value = "Загрузка на сервер..."
        status_text.color = "yellow"
        page.update()

        headers = {"Authorization": api_key}

        try:
            for item in selected_files:
                local_path = item["path"]
                new_filename = item["filename"]
                remote_path = f"{target_dir.rstrip('/cyrillyrikos.nekoweb.org')}/{new_filename}"

                with open(local_path, "rb") as f:
                    response = requests.post(
                        UPLOAD_URL, 
                        headers=headers, 
                        data={"pathname": remote_path}, 
                        files={"files": (new_filename, f)}
                    )
                    if response.status_code != 200:
                        status_text.value = f"Сбой загрузки файла: {item['orig_name']}"
                        status_text.color = "#ff4444"
                        page.update()
                        return
        except Exception as ex:
            status_text.value = f"Ошибка файлов: {ex}"
            status_text.color = "#ff4444"
            page.update()
            return

        full_post_html = post_content

        try:
            # СИНХРОНИЗАЦИЯ: Сначала пробуем стянуть актуальный фид с сайта, чтобы ничего не затереть
            existing_feed = ""
            try:
                feed_resp = requests.get(FEED_RAW_URL + "?" + str(uuid.uuid4()))
                if feed_resp.status_code == 200:
                    existing_feed = feed_resp.text
                elif os.path.exists(LOCAL_FEED_FILE):
                    with open(LOCAL_FEED_FILE, "r", encoding="utf-8") as f:
                        existing_feed = f.read()
            except Exception:
                if os.path.exists(LOCAL_FEED_FILE):
                    with open(LOCAL_FEED_FILE, "r", encoding="utf-8") as f:
                        existing_feed = f.read()

            updated_feed = f"{full_post_html}\n\n---\n\n{existing_feed}" if existing_feed.strip() else full_post_html
            with open(LOCAL_FEED_FILE, "w", encoding="utf-8") as f:
                f.write(updated_feed)

            # Очищаем старый фид на сервере перед загрузкой нового
            requests.post(DELETE_URL, headers=headers, data={"pathname": FEED_REMOTE_PATH})
            requests.post(DELETE_URL, headers=headers, data={"pathname": FEED_REMOTE_PATH, "isFolder": "true"})

            with open(LOCAL_FEED_FILE, "rb") as f:
                response = requests.post(
                    UPLOAD_URL, 
                    headers=headers, 
                    data={"pathname": FEED_REMOTE_PATH}, 
                    files={"files": ("feed.txt", f)}
                )
                if response.status_code == 200:
                    status_text.value = "Успешно опубликовано"
                    status_text.color = "white"
                    message_input.value = ""
                    selected_files.clear()
                    attachments_column.controls.clear()
                else:
                    status_text.value = f"Сбой сети: {response.status_code}"
                    status_text.color = "#ff4444"
        except Exception as ex:
            status_text.value = f"Ошибка публикации: {ex}"
            status_text.color = "#ff4444"

        page.update()

    page.add(
        ft.Container(
            content=ft.Column([
                ft.Text("Nekoweb Composer", size=15, weight=ft.FontWeight.BOLD, color="white", text_align=ft.TextAlign.CENTER),
                api_key_input,
                target_dir_input,
                ft.Divider(color="white", height=5),
                ft.Container(
                    content=ft.Column([
                        message_input,
                        attachments_column,
                        ft.Divider(color="#222222", height=1),
                        ft.Row([
                            ft.Button(
                                content="Прикрепить", 
                                color="white", 
                                bgcolor="#1a1a1a", 
                                on_click=pick_files_click
                            ),
                            ft.Button(
                                content="Опубликовать", 
                                color="white", 
                                bgcolor="#1a1a1a", 
                                on_click=send_message_ritual
                            )
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                    ], spacing=5),
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