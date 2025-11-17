import sys
import base64
import re
from io import BytesIO
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QTextEdit, QPushButton, QHBoxLayout,
    QVBoxLayout, QMessageBox, QFileDialog, QPlainTextEdit
)
from PyQt6.QtGui import QPixmap, QImage, QFont
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QMimeData
from PIL import Image, ImageFile
import binascii

# 允許 Pillow 容忍截斷的圖片
ImageFile.LOAD_TRUNCATED_IMAGES = True

class Base64EncoderThread(QThread):
    result_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, filepath):
        super().__init__()
        self.filepath = filepath

    def run(self):
        try:
            print(f"開始編碼文件: {self.filepath}")
            
            # 檢查文件是否存在
            import os
            if not os.path.exists(self.filepath):
                self.error_occurred.emit(f"文件不存在: {self.filepath}")
                return
            
            file_size = os.path.getsize(self.filepath)
            print(f"文件大小: {file_size} 字節")
            
            # 讀取文件數據
            with open(self.filepath, "rb") as f:
                data = f.read()
            
            print(f"實際讀取數據大小: {len(data)} 字節")
            
            if len(data) == 0:
                self.error_occurred.emit("文件為空或讀取失敗")
                return
            
            # 編碼為 Base64
            b64_str = base64.b64encode(data).decode('utf-8')
            print(f"Base64 編碼完成，長度: {len(b64_str)}")
            
            # 驗證編碼結果
            try:
                # 測試解碼以驗證編碼正確性
                test_decode = base64.b64decode(b64_str)
                if len(test_decode) != len(data):
                    self.error_occurred.emit("編碼驗證失敗：解碼後數據大小不匹配")
                    return
                print("Base64 編碼驗證成功")
            except Exception as verify_error:
                self.error_occurred.emit(f"編碼驗證失敗: {verify_error}")
                return
            
            self.result_ready.emit(b64_str)
            
        except Exception as e:
            print(f"編碼錯誤: {e}")
            self.error_occurred.emit(f"編碼錯誤: {e}")
            self.result_ready.emit("")

def pil_image_to_qpixmap(pil_img):
    try:
        if hasattr(pil_img, 'load'):
            pil_img.load()
        
        img_copy = pil_img.copy()

        if img_copy.mode != 'RGB':
            if img_copy.mode == 'I;16':
                img_copy = img_copy.point(lambda p: p * (1.0 / 256)).convert('L').convert('RGB')
            elif img_copy.mode in ('RGBA', 'LA') or (img_copy.mode == 'P' and 'transparency' in img_copy.info):
                background = Image.new('RGB', img_copy.size, (255, 255, 255))
                if img_copy.mode == 'RGBA':
                    background.paste(img_copy, mask=img_copy.split()[-1])
                elif img_copy.mode == 'LA':
                    background.paste(img_copy.convert('RGBA'), mask=img_copy.split()[-1])
                elif img_copy.mode == 'P':
                    img_copy = img_copy.convert('RGBA')
                    background.paste(img_copy, mask=img_copy.split()[-1])
                img_copy = background
            else:
                img_copy = img_copy.convert('RGB')

        img_copy.load()

        width, height = img_copy.size
        img_data = img_copy.tobytes("raw", "RGB")

        qimg = QImage(img_data, width, height, width * 3, QImage.Format.Format_RGB888)

        if qimg.isNull():
            raise Exception("QImage 創建失敗")

        pixmap = QPixmap.fromImage(qimg)

        if pixmap.isNull():
            raise Exception("QPixmap 創建失敗")

        print(f"成功轉換圖片: {width}x{height}, RGB 模式")
        return pixmap

    except Exception as e:
        print(f"圖片轉換失敗，嘗試備用方法: {e}")
        try:
            buffer = BytesIO()

            if img_copy.mode != 'RGB':
                if img_copy.mode in ('RGBA', 'LA'):
                    background = Image.new('RGB', img_copy.size, (255, 255, 255))
                    background.paste(img_copy, mask=img_copy.split()[-1])
                    img_copy = background
                else:
                    img_copy = img_copy.convert('RGB')

            img_copy.save(buffer, format='JPEG', quality=100)
            buffer.seek(0)

            pixmap = QPixmap()
            success = pixmap.loadFromData(buffer.getvalue())
            buffer.close()

            if success and not pixmap.isNull():
                print("備用方法轉換成功")
                return pixmap
            else:
                print("備用方法也失敗")
                return QPixmap()

        except Exception as e2:
            print(f"備用方法也失敗: {e2}")
            return QPixmap()

def clean_base64_string(base64_string: str) -> str:
    """清理和驗證 Base64 字符串"""
    # 移除所有空白字符（空格、換行、制表符等）
    base64_string = re.sub(r'\s', '', base64_string)
    
    # 移除可能的 data URL 前綴（如 data:image/png;base64,）
    if 'base64,' in base64_string:
        base64_string = base64_string.split('base64,')[-1]
    
    # 只保留有效的 Base64 字符
    base64_string = re.sub(r'[^A-Za-z0-9+/=]', '', base64_string)
    
    # 檢查字符串長度
    if len(base64_string) == 0:
        print("Base64 字符串為空")
        return ""
    
    # 補齊 padding
    missing_padding = len(base64_string) % 4
    if missing_padding:
        base64_string += '=' * (4 - missing_padding)
    
    return base64_string

def validate_base64(base64_string: str) -> bool:
    """驗證 Base64 字符串的有效性"""
    try:
        # 嘗試解碼前幾個字節來驗證
        base64.b64decode(base64_string[:100], validate=True)
        return True
    except Exception as e:
        print(f"Base64 驗證失敗: {e}")
        return False


def base64_to_image(b64_str):
    """改進的 Base64 轉圖片函數"""
    try:
        print(f"開始處理 Base64，原始長度: {len(b64_str)}")
        
        # 清理 Base64 字符串
        cleaned_b64 = clean_base64_string(b64_str)
        print(f"清理後長度: {len(cleaned_b64)}")
        
        if len(cleaned_b64) < 100:  # Base64 編碼的圖片通常會很長
            print("Base64 字符串太短，可能不是有效的圖片編碼")
            return None
        
        # 驗證 Base64 格式
        if not validate_base64(cleaned_b64):
            print("Base64 格式驗證失敗")
            return None
        
        # 解碼 Base64
        try:
            img_data = base64.b64decode(cleaned_b64, validate=True)
            print(f"解碼後數據大小: {len(img_data)} 字節")
        except binascii.Error as e:
            print(f"Base64 解碼錯誤: {e}")
            return None
        except Exception as e:
            print(f"解碼過程中發生錯誤: {e}")
            return None
        
        if len(img_data) < 100:  # 圖片數據通常會比這個大得多
            print("解碼後的數據太小，可能不是有效的圖片")
            return None
        
        # 檢查圖片文件頭
        img_headers = {
            b'\xFF\xD8\xFF': 'JPEG',
            b'\x89PNG\r\n\x1a\n': 'PNG',
            b'GIF87a': 'GIF87a',
            b'GIF89a': 'GIF89a',
            b'BM': 'BMP',
            b'RIFF': 'WebP',
            b'II*\x00': 'TIFF',
            b'MM\x00*': 'TIFF'
        }
        
        detected_format = None
        for header, format_name in img_headers.items():
            if img_data.startswith(header) or (header == b'RIFF' and b'WEBP' in img_data[:12]):
                detected_format = format_name
                print(f"檢測到圖片格式: {format_name}")
                break
        
        if not detected_format:
            print("警告: 未檢測到已知的圖片格式標頭，但嘗試繼續處理...")
        
        # 創建 BytesIO 對象並嘗試打開圖片
        img_buffer = BytesIO(img_data)
        
        try:
            # 嘗試用 PIL 打開圖片
            img = Image.open(img_buffer)
            print(f"PIL 成功打開圖片: 模式={img.mode}, 大小={img.size}, 格式={img.format}")
            
            # 強制加載圖片數據
            img.load()
            
            # 創建副本以避免問題
            img_copy = img.copy()
            
            # 關閉緩沖區
            img_buffer.close()
            
            print(f"圖片處理完成: {img_copy.mode}, {img_copy.size}")
            return img_copy
            
        except Exception as pil_error:
            print(f"PIL 打開圖片失敗: {pil_error}")
            img_buffer.close()
            return None
            
    except Exception as e:
        print(f"Base64 轉圖片過程中發生未預期的錯誤: {e}")
        return None


class Base64ConverterApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Base64編碼")
        self.resize(950, 550)
        self.setAcceptDrops(True)
        self.current_pil_img = None
        self.thread = None
        self.is_closing = False
        self.init_ui()

    def init_ui(self):
        self.label_image = QLabel("拉曳圖片到此", alignment=Qt.AlignmentFlag.AlignCenter)
        self.label_image.setStyleSheet("background-color: black; border: 3px; color: #ccc; font-size: 20px;")
        self.label_image.setFixedSize(400, 400)

        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText("Base64 編碼會顯示在這裡，或在這裡貼上 Base64 編碼")

        font = QFont()
        font.setPointSize(14)
        self.text_edit.setFont(font)

        self.btn_copy = QPushButton("複製 Base64")
        self.btn_copy.clicked.connect(self.copy_base64)

        self.btn_decode = QPushButton("Base64 → 顯示圖片")
        self.btn_decode.clicked.connect(self.decode_base64_to_image)

        # 新增下載按鈕
        self.btn_download = QPushButton("下載圖片")
        self.btn_download.clicked.connect(self.download_image)
        self.btn_download.setEnabled(False)  # 初始狀態為禁用

        # 新增清除按鈕
        self.btn_clear = QPushButton("清除")
        self.btn_clear.clicked.connect(self.clear_all)

        btn_layout1 = QHBoxLayout()
        btn_layout1.addWidget(self.btn_copy)
        btn_layout1.addWidget(self.btn_decode)

        btn_layout2 = QHBoxLayout()
        btn_layout2.addWidget(self.btn_download)
        btn_layout2.addWidget(self.btn_clear)

        right_layout = QVBoxLayout()
        right_layout.addWidget(self.text_edit)
        right_layout.addLayout(btn_layout1)
        right_layout.addLayout(btn_layout2)

        main_layout = QHBoxLayout()
        main_layout.addWidget(self.label_image)
        main_layout.addLayout(right_layout)

        self.setLayout(main_layout)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if not urls:
            return
        filepath = urls[0].toLocalFile()
        
        print(f"拖放文件: {filepath}")
        
        # 檢查文件擴展名
        if not filepath.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp', '.tiff')):
            QMessageBox.warning(self, "錯誤", "請拖放有效的圖片檔案")
            return

        # 檢查文件是否存在
        import os
        if not os.path.exists(filepath):
            QMessageBox.warning(self, "錯誤", "文件不存在")
            return

        try:
            # 嘗試用 PIL 打開圖片以驗證
            print("正在驗證圖片...")
            pil_img = Image.open(filepath)
            pil_img.verify()  # 驗證圖片完整性
            
            # 重新打開圖片（verify 後需要重新打開）
            pil_img = Image.open(filepath)
            pil_img.load()
            self.current_pil_img = pil_img.copy()  # 創建副本
            
            print(f"圖片驗證成功: {pil_img.mode}, {pil_img.size}, {pil_img.format}")
            
            # 顯示圖片
            pixmap = pil_image_to_qpixmap(self.current_pil_img)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(400, 400, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.label_image.setPixmap(scaled_pixmap)
                self.btn_download.setEnabled(True)  # 啟用下載按鈕
                print("圖片顯示成功")
            else:
                raise Exception("圖片轉換為 QPixmap 失敗")
                
        except Exception as e:
            print(f"圖片處理失敗: {e}")
            QMessageBox.warning(self, "錯誤", f"圖片載入失敗: {e}")
            return

        # 開始編碼
        self.text_edit.setPlainText("正在編碼，請稍候...")
        print("開始 Base64 編碼...")
        
        # 確保之前的線程已經結束
        if self.thread is not None and self.thread.isRunning():
            print("等待之前的線程結束...")
            try:
                self.thread.result_ready.disconnect()
                self.thread.error_occurred.disconnect()
            except:
                pass
            self.thread.quit()
            self.thread.wait()
            
        self.thread = Base64EncoderThread(filepath)
        self.thread.result_ready.connect(self.on_encode_finished)
        self.thread.error_occurred.connect(self.on_encode_error)
        self.thread.start()

    def on_encode_finished(self, b64_str):
        if self.is_closing:
            return
            
        if not b64_str:
            QMessageBox.warning(self, "錯誤", "編碼失敗")
            self.text_edit.setPlainText("")
            return

        print(f"編碼完成，開始顯示 Base64 (長度: {len(b64_str)})")
        self.insert_text_in_chunks(b64_str)
        print("Base64 顯示完成")

    def on_encode_error(self, error_msg):
        """處理編碼錯誤"""
        if self.is_closing:
            return
        QMessageBox.warning(self, "編碼錯誤", error_msg)
        self.text_edit.setPlainText("")

    def insert_text_in_chunks(self, text, chunk_size=4096):
        # 改成直接一次設置全部文字，避免分段問題
        if self.is_closing:
            return
        self.text_edit.setPlainText(text)

    def copy_base64(self):
        text = self.text_edit.toPlainText().strip()
        if text:
            clipboard = QApplication.clipboard()
            clipboard.setText(text)  # 直接設置純文字
            QMessageBox.information(self, "提示", "Base64 已複製到剪貼簿")
        else:
            QMessageBox.warning(self, "警告", "Base64 編碼為空")

    def decode_base64_to_image(self):
        """解碼 Base64 為圖片並顯示 - 修復版本"""
        b64_str = self.text_edit.toPlainText().strip()
        if not b64_str:
            QMessageBox.warning(self, "警告", "請先輸入 Base64 編碼")
            return
        
        print("=" * 50)
        print("開始解碼 Base64...")
        print(f"輸入長度: {len(b64_str)}")
        print(f"前100個字符: {b64_str[:100]}")
        
        # 使用改進的解碼函數
        pil_img = base64_to_image(b64_str)
        if pil_img is None:
            QMessageBox.warning(
                self, 
                "錯誤", 
                "Base64 編碼無法轉換為圖片\n\n可能的原因：\n"
                "1. Base64 編碼不完整或損壞\n"
                "2. 編碼中包含無效字符\n"
                "3. 不是有效的圖片格式\n"
                "4. 數據被截斷\n\n"
                "請檢查 Base64 編碼是否完整且正確"
            )
            return
            
        try:
            # 保存解碼後的圖片
            self.current_pil_img = pil_img.copy()
            
            # 轉換並顯示圖片
            pixmap = pil_image_to_qpixmap(self.current_pil_img)
            
            if pixmap.isNull():
                raise Exception("無法轉換為 QPixmap")
            
            scaled_pixmap = pixmap.scaled(400, 400, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.label_image.setPixmap(scaled_pixmap)
            self.btn_download.setEnabled(True)  # 啟用下載按鈕
            
            print("圖片解碼並顯示成功")
            
        except Exception as e:
            print(f"圖片顯示失敗: {e}")
            QMessageBox.warning(self, "錯誤", f"圖片顯示失敗: {e}")
            # 即使顯示失敗，也保存解碼成功的圖片數據
            self.current_pil_img = pil_img.copy()
            self.btn_download.setEnabled(True)

    def download_image(self):
        """下載當前顯示的圖片"""
        if self.current_pil_img is None:
            QMessageBox.warning(self, "警告", "沒有可下載的圖片")
            return
        
        # 開啟文件保存對話框
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "保存圖片",
            "image.png",
            "PNG files (*.png);;JPEG files (*.jpg);;All files (*.*)"
        )
        
        if not file_path:
            return  # 用戶取消了保存
        
        try:
            # 根據文件擴展名決定保存格式
            if file_path.lower().endswith(('.jpg', '.jpeg')):
                # JPEG 不支持透明度，需要轉換為 RGB
                if self.current_pil_img.mode == "RGBA":
                    # 創建白色背景
                    background = Image.new('RGB', self.current_pil_img.size, (255, 255, 255))
                    background.paste(self.current_pil_img, mask=self.current_pil_img.split()[-1])
                    background.save(file_path, "JPEG", quality=95)
                else:
                    rgb_img = self.current_pil_img.convert("RGB")
                    rgb_img.save(file_path, "JPEG", quality=95)
            else:
                # PNG 或其他格式
                self.current_pil_img.save(file_path, "PNG")
            QMessageBox.information(self, "成功", f"圖片已保存到: {file_path}")
        except Exception as e:
            QMessageBox.warning(self, "錯誤", f"保存圖片失敗: {e}")

    def clear_all(self):

        self.text_edit.clear()  # 或 self.text_edit.setPlainText("")
        self.text_edit.setPlaceholderText("Base64 編碼會顯示在這裡，或在這裡貼上 Base64 編碼")
        
        # 重置圖片顯示區域
        self.label_image.clear()
        self.label_image.setText("拖放圖片到此")
        self.label_image.setStyleSheet("background-color: black; border: 3px; color: #ccc; font-size: 20px;")
        # 清除當前圖片數據
        if self.current_pil_img:
            try:
                self.current_pil_img.close()
            except:
                pass
        self.current_pil_img = None
        
        # 禁用下載按鈕
        self.btn_download.setEnabled(False)
        
        print("已清除所有內容")

    def closeEvent(self, event):
        """正確處理程式關閉事件"""
        print("正在關閉程式...")
        
        self.is_closing = True
        
        if self.thread is not None and self.thread.isRunning():
            print("等待編碼線程結束...")
            try:
                self.thread.result_ready.disconnect()
            except:
                pass
            
            self.thread.quit()
            if not self.thread.wait(2000):
                print("強制終止線程")
                self.thread.terminate()
                self.thread.wait(1000)
        
        # 清理資源
        if self.current_pil_img:
            try:
                self.current_pil_img.close()
            except:
                pass
        
        event.accept()
        print("程式已關閉")
        
        QApplication.instance().quit()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    
    win = Base64ConverterApp()
    win.show()
    
    try:
        exit_code = app.exec()
        print(f"程式正常退出，退出碼: {exit_code}")
    except KeyboardInterrupt:
        print("收到中斷信號，正在退出...")
    finally:
        if app:
            app.quit()
        sys.exit(0)