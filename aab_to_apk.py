import subprocess
import os
import sys
import threading
import queue
import shutil
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext

# =================================================================
#
#  AAB/APKS 轉換與安裝工具 (GUI版)
#  by Gemini
#
# =================================================================

# --- 1. 設定區塊 ---
BUNDLETOOL_JAR = 'bundletool-all-1.13.2.jar'
KEYSTORE_FILE = 'key'
KEY_ALIAS = 'key'
STORE_PASS = '00000000'
KEY_PASS = '00000000'


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("AAB/APKS 工具 by Gemini")
        self.root.geometry("800x700")

        self.aab_file_path = tk.StringVar()
        self.apks_file_path = tk.StringVar()
        self.adb_port = tk.StringVar(value="5555")
        self.last_apks_path = None
        self.log_queue = queue.Queue()

        main_frame = ttk.Frame(root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        convert_frame = ttk.LabelFrame(main_frame, text="1. AAB -> APKS 轉換 (如果需要)", padding="10")
        convert_frame.pack(fill=tk.X, pady=5)
        aab_select_frame = ttk.Frame(convert_frame)
        aab_select_frame.pack(fill=tk.X)
        aab_label = ttk.Label(aab_select_frame, text="AAB 檔案:")
        aab_label.pack(side=tk.LEFT, padx=(0, 5))
        self.aab_path_entry = ttk.Entry(aab_select_frame, textvariable=self.aab_file_path, state='readonly')
        self.aab_path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.select_aab_button = ttk.Button(aab_select_frame, text="選擇 AAB...", command=self.select_aab_file)
        self.select_aab_button.pack(side=tk.LEFT, padx=(5, 0))
        self.convert_button = ttk.Button(convert_frame, text="🚀 開始轉換", command=self.start_conversion)
        self.convert_button.pack(pady=10, fill=tk.X, side=tk.BOTTOM)

        install_frame = ttk.LabelFrame(main_frame, text="2. APKS 安裝到模擬器", padding="10")
        install_frame.pack(fill=tk.X, pady=10)
        apks_select_frame = ttk.Frame(install_frame)
        apks_select_frame.pack(fill=tk.X, pady=(0, 10))
        apks_label = ttk.Label(apks_select_frame, text="APKS 檔案:")
        apks_label.pack(side=tk.LEFT, padx=(0, 5))
        self.apks_path_entry = ttk.Entry(apks_select_frame, textvariable=self.apks_file_path, state='readonly')
        self.apks_path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.select_apks_button = ttk.Button(apks_select_frame, text="選擇 APKS...", command=self.select_apks_file)
        self.select_apks_button.pack(side=tk.LEFT, padx=(5, 0))
        adb_frame = ttk.Frame(install_frame)
        adb_frame.pack(fill=tk.X)
        adb_label = ttk.Label(adb_frame, text="BS 模擬器 Port (127.0.0.1:):")
        adb_label.pack(side=tk.LEFT, padx=(0, 5))
        self.adb_port_entry = ttk.Entry(adb_frame, textvariable=self.adb_port, width=15)
        self.adb_port_entry.pack(side=tk.LEFT, padx=(0, 10))
        self.install_button = ttk.Button(adb_frame, text="📲 安裝到模擬器", command=self.start_installation, state='disabled')
        self.install_button.pack(side=tk.LEFT, fill=tk.X, expand=True)

        log_frame = ttk.LabelFrame(main_frame, text="執行日誌", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True)
        self.log_area = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, state='disabled', height=20)
        self.log_area.pack(fill=tk.BOTH, expand=True)

        self.process_log_queue()

    def select_aab_file(self):
        filepath = filedialog.askopenfilename(title="請選擇一個 .aab 檔案", filetypes=[("Android App Bundle", "*.aab")])
        if filepath:
            self.aab_file_path.set(filepath)
            self.log_message(f"已選擇 AAB 檔案: {filepath}\n")
            self.apks_file_path.set("")
            self.last_apks_path = None
            self.install_button.config(state='disabled')

    def select_apks_file(self):
        filepath = filedialog.askopenfilename(title="請選擇一個 .apks 檔案", filetypes=[("APK Set Archive", "*.apks")])
        if filepath:
            self.apks_file_path.set(filepath)
            self.last_apks_path = filepath
            self.log_message(f"已直接選擇 APKS 檔案: {filepath}\n")
            self.install_button.config(state='normal')

    def log_message(self, message):
        self.log_area.config(state='normal')
        self.log_area.insert(tk.END, message)
        self.log_area.see(tk.END)
        self.log_area.config(state='disabled')

    def set_ui_state(self, is_busy):
        state = 'disabled' if is_busy else 'normal'
        self.convert_button.config(state=state)
        self.select_aab_button.config(state=state)
        self.select_apks_button.config(state=state)
        if not is_busy and self.last_apks_path:
            self.install_button.config(state='normal')
        else:
            self.install_button.config(state='disabled')

    def start_conversion(self):
        aab_path = self.aab_file_path.get()
        if not aab_path:
            self.log_message("錯誤: 請先選擇一個 AAB 檔案！\n")
            return
        if not all(os.path.exists(f) for f in [BUNDLETOOL_JAR, KEYSTORE_FILE]):
            self.log_message(f"錯誤: 找不到 {BUNDLETOOL_JAR} 或 '{KEYSTORE_FILE}'。\n")
            return
        self.set_ui_state(is_busy=True)
        self.convert_button.config(text="轉換中...")
        self.log_area.config(state='normal')
        self.log_area.delete('1.0', tk.END)
        self.log_area.config(state='disabled')
        thread = threading.Thread(target=self.conversion_worker, args=(aab_path,), daemon=True)
        thread.start()

    def conversion_worker(self, aab_path):
        self.last_apks_path = None
        try:
            output_apks_name = os.path.splitext(aab_path)[0] + '.apks'
            self.log_queue.put("========================================\n")
            self.log_queue.put(f"🚀 開始轉換: {os.path.basename(aab_path)}\n")
            self.log_queue.put(f"   輸出檔案: {os.path.basename(output_apks_name)}\n")
            self.log_queue.put("========================================\n\n")
            command = ['java', '-jar', BUNDLETOOL_JAR, 'build-apks', f'--bundle={aab_path}', f'--output={output_apks_name}', '--mode=universal', f'--ks={KEYSTORE_FILE}', f'--ks-key-alias={KEY_ALIAS}', f'--ks-pass=pass:{STORE_PASS}', f'--key-pass=pass:{KEY_PASS}', '--overwrite']
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace', creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
            for line in iter(process.stdout.readline, ''): self.log_queue.put(line)
            process.stdout.close()
            return_code = process.wait()
            if return_code != 0:
                self.log_queue.put(f"\n--- ❌ 錯誤 --- \n{process.stderr.read()}\n")
                self.log_queue.put("\n轉換失敗！😥 請檢查上面的錯誤訊息。\n")
            else:
                self.last_apks_path = output_apks_name
                self.apks_file_path.set(output_apks_name)
                self.log_queue.put("\n--- ✅ 完成 --- \n🎉 轉換成功！\n")
                self.log_queue.put(f"輸出的 '{os.path.basename(output_apks_name)}' 已產生。\n")
                self.log_queue.put("現在可以點擊按鈕安裝到模擬器。\n")
        except Exception as e:
            self.log_queue.put(f"發生未預期的錯誤: {e}\n")
        finally:
            self.log_queue.put("CONVERT_DONE")

    def start_installation(self):
        if not self.last_apks_path:
            self.log_message("錯誤: 請先成功轉換或選擇一個 APKS 檔案。\n")
            return
        port = self.adb_port.get().strip()
        if not port.isdigit():
            self.log_message(f"錯誤: Port '{port}' 不是一個有效的數字。\n")
            return
        self.set_ui_state(is_busy=True)
        self.install_button.config(text="安裝中...")
        self.log_message("\n========================================\n")
        self.log_message(f"📲 開始安裝到模擬器 127.0.0.1:{port}\n")
        self.log_message("========================================\n\n")
        thread = threading.Thread(target=self.installation_worker, args=(port,), daemon=True)
        thread.start()

    def installation_worker(self, port):
        try:
            adb_path = shutil.which('adb')
            if not adb_path:
                self.log_queue.put("錯誤: 找不到 'adb' 指令。\n請確認已安裝 Android SDK Platform-Tools 並將其路徑加入系統環境變數中。\n")
                return

            device_id = f'127.0.0.1:{port}'

            self.log_queue.put(f"找到 ADB 路徑: {adb_path}\n")
            self.log_queue.put(f"目標裝置 ID: {device_id}\n")

            self.log_queue.put(f"正在連接 adb 到 {device_id}...\n")
            adb_connect_cmd = [adb_path, 'connect', device_id]
            connect_result = subprocess.run(adb_connect_cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')

            if connect_result.returncode != 0 or "unable to connect" in connect_result.stdout.lower() or "failed to connect" in connect_result.stdout.lower():
                self.log_queue.put(f"--- ❌ ADB 連接失敗 ---\n{connect_result.stdout}\n{connect_result.stderr}\n")
                self.log_queue.put("請確認：\n1. 模擬器已開啟。\n2. 模擬器設定中的 ADB 功能已啟用。\n3. Port 號碼正確。\n")
                return

            self.log_queue.put(f"ADB 連接成功: {connect_result.stdout.strip()}\n")
            self.log_queue.put(f"正在安裝: {os.path.basename(self.last_apks_path)} 到裝置 {device_id}...\n")

            # ✅✅✅ --- 主要修改點在這裡 --- ✅✅✅
            # 將 device_id 加入 install-apks 指令中
            install_cmd = [
                'java', '-jar', BUNDLETOOL_JAR, 'install-apks',
                f'--apks={self.last_apks_path}',
                f'--adb={adb_path}',
                f'--device-id={device_id}'  # <-- 新增這行指定裝置
            ]
            install_process = subprocess.Popen(install_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace', creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)

            for line in iter(install_process.stdout.readline, ''): self.log_queue.put(line)
            install_process.stdout.close()
            return_code = install_process.wait()

            if return_code != 0:
                self.log_queue.put(f"\n--- ❌ 安裝失敗 ---\n{install_process.stderr.read()}\n")
            else:
                self.log_queue.put("\n--- ✅ 完成 --- \n🎉 App 已成功安裝到模擬器！\n")
        except Exception as e:
            self.log_queue.put(f"發生未預期的錯誤: {e}\n")
        finally:
            self.log_queue.put("INSTALL_DONE")

    def process_log_queue(self):
        try:
            while True:
                message = self.log_queue.get_nowait()
                if message == "CONVERT_DONE":
                    self.set_ui_state(is_busy=False)
                    self.convert_button.config(text="🚀 開始轉換")
                elif message == "INSTALL_DONE":
                    self.set_ui_state(is_busy=False)
                    self.install_button.config(text="📲 安裝到模擬器")
                else:
                    self.log_message(message)
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.process_log_queue)


if __name__ == '__main__':
    root = tk.Tk()
    app = App(root)
    root.mainloop()

