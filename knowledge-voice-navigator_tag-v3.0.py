# -*- coding: utf-8 -*-
"""
知识库语音导航系统
v 1.0.0
Copyright (c) 2025 zhangh
"""

import os
import re
import sys
import time
import threading
import tkinter as tk
from tkinter import filedialog, scrolledtext, ttk, messagebox
import difflib

# 尝试导入可选依赖项
try:
    import speech_recognition as sr

    SPEECH_AVAILABLE = True
except ImportError:
    SPEECH_AVAILABLE = False

try:
    import jieba

    JIEBA_AVAILABLE = True
except ImportError:
    JIEBA_AVAILABLE = False

try:
    import nltk
    from nltk.tokenize import word_tokenize

    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        nltk.download('punkt', quiet=True)
    try:
        nltk.data.find('corpora/stopwords')
    except LookupError:
        nltk.download('stopwords', quiet=True)
    from nltk.corpus import stopwords

    NLTK_AVAILABLE = True
except ImportError:
    NLTK_AVAILABLE = False

try:
    from vosk import Model, KaldiRecognizer
    import json

    VOSK_AVAILABLE = True
except ImportError:
    VOSK_AVAILABLE = False


# 创建自定义无声消息框
class SilentMessageBox:
    def __init__(self, root):
        self.root = root

    def showinfo(self, title, message):
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.transient(self.root)
        dialog.grab_set()

        # 计算合适的窗口大小
        max_line_length = max(len(line) for line in message.split('\n'))
        width = min(max(300, max_line_length * 7), 500)
        height = min(200 + message.count('\n') * 20, 400)

        dialog.geometry(f"{width}x{height}")

        # 添加消息文本
        text = scrolledtext.ScrolledText(dialog, wrap=tk.WORD)
        text.insert(tk.END, message)
        text.config(state=tk.DISABLED)
        text.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # 添加确定按钮
        ok_button = tk.Button(dialog, text="确定", width=10, command=dialog.destroy)
        ok_button.pack(pady=10)

        # 将焦点设置到确定按钮
        ok_button.focus_set()

        # 按Esc或回车关闭对话框
        dialog.bind("<Escape>", lambda e: dialog.destroy())
        dialog.bind("<Return>", lambda e: dialog.destroy())

        # 设置为模态对话框
        self.root.wait_window(dialog)

    def showwarning(self, title, message):
        self.showinfo(title, message)

    def showerror(self, title, message):
        self.showinfo(title, message)
# 禁用系统提示音 - 增强版
def disable_system_sounds():
    try:
        if sys.platform == 'win32':
            # 禁用MessageBeep
            import ctypes
            MessageBeep = ctypes.windll.user32.MessageBeep
            MessageBeep.argtypes = [ctypes.c_uint]
            MessageBeep.restype = ctypes.c_bool

            def silent_message_beep(beep_type=0):
                return True

            ctypes.windll.user32.MessageBeep = silent_message_beep

            # 尝试禁用系统通知声音设置
            try:
                import winreg
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                     r"Control Panel\Sound",
                                     0,
                                     winreg.KEY_SET_VALUE)
                winreg.SetValueEx(key, "Beep", 0, winreg.REG_SZ, "no")
                winreg.SetValueEx(key, "ExtendedSounds", 0, winreg.REG_SZ, "no")
                winreg.CloseKey(key)
            except:
                print("无法修改系统声音注册表设置，但已禁用MessageBeep")

        # 将Tkinter配置为不使用系统铃声
        try:
            root = tk._default_root
            if root:
                root.option_add('*bell', False)
        except:
            print("无法禁用Tkinter铃声")

    except Exception as e:
        print(f"禁用系统提示音失败: {e}")


class KnowledgeNavigator:
    def __init__(self, root):
        self.root = root
        self.root.title("知识库语音导航系统")
        self.root.geometry("1200x800")

        # 程序状态
        self.knowledge_base = ""
        self.knowledge_path = None
        self.heading_positions = []  # 存储所有标题及其位置
        self.current_matches = []
        self.listening = False
        self.speech_engine = "Google"  # 默认使用Google
        self.fuzzy_ratio = 70  # 默认模糊匹配阈值

        # 创建无声消息框
        self.messagebox = SilentMessageBox(root)

        # 语音相关状态
        if SPEECH_AVAILABLE:
            self.recognizer = sr.Recognizer()
            self.mic = sr.Microphone()

            # 改进的语音识别参数
            # self.recognizer.dynamic_energy_threshold = True  # 动态阈值
            # # self.recognizer.energy_threshold = 300  # 降低麦克风阈值，更容易捕获声音
            # self.recognizer.energy_threshold = 150  # 降低麦克风阈值，更容易捕获声音
            # self.recognizer.pause_threshold = 0.6  # 增加停顿阈值，适应更长的句子
            self.recognizer.dynamic_energy_threshold = False  # 禁用动态阈值
            self.recognizer.energy_threshold = 100  # 大幅降低阈值，更容易捕获声音
            self.recognizer.pause_threshold = 0.5  # 略微减少暂停阈值

        # Vosk相关状态
        self.vosk_model = None

        # 长对话相关
        self.audio_buffer = []
        self.max_buffer_size = 5  # 保存的音频段数量
        self.text_history = []

        # 标签相关属性 - 确保放在create_ui()调用前
        self.tags = []  # List to store search keyword tags
        self.tag_buttons = []  # List to store tag button widgets
        self.tag_frame = None  # Frame to hold the tags
        self.tag_frame_main = None  # Main container for the tag frame

        # 创建界面
        self.create_ui()

        # 在界面创建完成后初始化标签
        self.load_tags()  # This will load saved tags or initialize defaults
        self.create_tag_frame()

        # 显示欢迎信息
        self.content_text.config(state=tk.NORMAL)
        self.content_text.delete(1.0, tk.END)
        welcome_text = """
# 欢迎使用知识库语音导航系统

## 基本使用方法
1. 点击"文件"→"打开知识库"加载Markdown或文本文件
2. 在搜索框输入关键词或点击"开始监听"使用语音搜索
3. 点击左侧的匹配结果跳转到相应位置
4. 或使用右侧的目录直接导航到相应章节

## 特色功能
* 支持模糊匹配搜索
* 语音控制导航
* 自动识别文档结构
* 长对话理解模式

请开始使用吧！
"""
        self.content_text.insert(tk.END, welcome_text)
        self.content_text.config(state=tk.DISABLED)

        # 在其他初始化代码旁边添加
        self.ac_listbox = None
        self.search_history = []

    def create_ui(self):
        """创建用户界面"""
        # 创建菜单栏
        self.menu_bar = tk.Menu(self.root)
        self.root.config(menu=self.menu_bar)

        # 文件菜单
        self.file_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="文件", menu=self.file_menu)
        self.file_menu.add_command(label="打开知识库", command=self.open_knowledge_base)
        self.file_menu.add_command(label="重新加载", command=self.reload_knowledge_base, state=tk.DISABLED)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="退出", command=self.root.quit)

        # 设置菜单
        self.settings_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="设置", menu=self.settings_menu)


        # 语音引擎菜单
        self.voice_menu = tk.Menu(self.settings_menu, tearoff=0)
        self.settings_menu.add_cascade(label="语音识别引擎", menu=self.voice_menu)

        # 语音引擎选项
        self.engine_var = tk.StringVar(value="Google")
        self.voice_menu.add_radiobutton(label="Google (在线，准确度高)",
                                        variable=self.engine_var,
                                        value="Google",
                                        command=self.change_speech_engine)
        self.voice_menu.add_radiobutton(label="Sphinx (离线，速度快)",
                                        variable=self.engine_var,
                                        value="Sphinx",
                                        command=self.change_speech_engine)

        # 如果Vosk可用，添加Vosk选项
        if VOSK_AVAILABLE:
            self.voice_menu.add_radiobutton(label="Vosk (离线，中文支持好)",
                                            variable=self.engine_var,
                                            value="Vosk",
                                            command=self.change_speech_engine)
            self.settings_menu.add_command(label="下载Vosk模型", command=self.download_vosk_model)

        # 诊断语音识别
        self.settings_menu.add_separator()
        self.settings_menu.add_command(label="诊断语音识别", command=self.diagnose_speech_recognition)

        # 搜索设置菜单
        self.search_menu = tk.Menu(self.settings_menu, tearoff=0)
        self.settings_menu.add_cascade(label="搜索设置", menu=self.search_menu)

        # 模糊匹配选项
        self.fuzzy_match_var = tk.BooleanVar(value=True)
        self.search_menu.add_checkbutton(label="启用模糊匹配",
                                         variable=self.fuzzy_match_var)

        # 模糊匹配灵敏度设置
        self.settings_menu.add_command(label="模糊匹配灵敏度", command=self.show_sensitivity_dialog)

        # 视图菜单
        self.view_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="视图", menu=self.view_menu)
        self.view_menu.add_command(label="放大字体", command=self.increase_font_size)
        self.view_menu.add_command(label="缩小字体", command=self.decrease_font_size)
        self.view_menu.add_separator()
        self.view_menu.add_command(label="展开所有目录", command=lambda: self.expand_all_toc(True))
        self.view_menu.add_command(label="折叠所有目录", command=lambda: self.expand_all_toc(False))

        # 帮助菜单
        self.help_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="帮助", menu=self.help_menu)
        self.help_menu.add_command(label="使用帮助", command=self.show_help)
        self.help_menu.add_command(label="关于", command=self.show_about)

        # 创建顶部控制面板
        self.control_frame = tk.Frame(self.root, pady=10)
        self.control_frame.pack(fill=tk.X, padx=10)

        # 添加监听开关按钮
        self.listen_button = tk.Button(
            self.control_frame,
            text="开始监听",
            command=self.toggle_listening,
            width=10,
            height=1,
            bg="green",
            fg="white",
            state=tk.DISABLED if not SPEECH_AVAILABLE else tk.NORMAL
        )
        self.listen_button.pack(side=tk.LEFT, padx=10)

        # 添加处理长对话按钮
        self.process_long_button = tk.Button(
            self.control_frame,
            text="处理长对话",
            command=self.process_long_conversation,
            width=12,
            height=1,
            bg="blue",
            fg="white",
            state=tk.DISABLED
        )
        self.process_long_button.pack(side=tk.LEFT, padx=5)

        # 搜索框
        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(self.control_frame, textvariable=self.search_var, width=30)
        self.search_entry.pack(side=tk.LEFT, padx=10)
        self.search_entry.bind('<Return>', lambda e: self.manual_search())

        # 设置自动完成功能
        # self.setup_autocomplete()

        self.search_button = tk.Button(
            self.control_frame,
            text="搜索",
            command=self.manual_search,
            height=1
        )
        self.search_button.pack(side=tk.LEFT, padx=5)

        # 清除搜索按钮
        self.clear_button = tk.Button(
            self.control_frame,
            text="清除",
            command=self.clear_search,
            height=1
        )
        self.clear_button.pack(side=tk.LEFT, padx=5)

        # 状态标签
        self.status_label = tk.Label(self.control_frame, text="状态: 未加载知识库")
        self.status_label.pack(side=tk.RIGHT, padx=10)

        # 创建标签框架 - 紧接着控制面板之后
        self.create_tag_frame()

        # 创建主内容区 - 使用PanedWindow
        self.main_paned = tk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.main_paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 左侧：匹配结果列表
        self.match_frame = tk.Frame(self.main_paned, width=300)
        self.match_frame.pack_propagate(False)  # 防止frame被内容撑开

        self.match_label = tk.Label(self.match_frame, text="匹配结果:")
        self.match_label.pack(anchor=tk.W, padx=5, pady=5)

        # 创建带滚动条的匹配列表
        match_list_frame = tk.Frame(self.match_frame)
        match_list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.match_list = tk.Listbox(match_list_frame, width=40)
        match_scrollbar = tk.Scrollbar(match_list_frame, orient=tk.VERTICAL, command=self.match_list.yview)
        self.match_list.config(yscrollcommand=match_scrollbar.set)
        match_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.match_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.match_list.bind('<<ListboxSelect>>', self.on_match_select)

        self.main_paned.add(self.match_frame)

        # 中间：知识库内容显示
        self.content_frame = tk.Frame(self.main_paned)

        # 创建带滚动条的文本区域
        self.content_text = scrolledtext.ScrolledText(
            self.content_frame,
            wrap=tk.WORD,
            width=70,
            height=30,
            font=("Courier New", 11)
        )
        self.content_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.content_text.config(state=tk.DISABLED)  # 只读模式

        self.main_paned.add(self.content_frame)

        # 右侧：目录树
        self.toc_frame = tk.Frame(self.main_paned, width=200)
        self.toc_frame.pack_propagate(False)  # 防止frame被内容撑开

        self.toc_label = tk.Label(self.toc_frame, text="目录:")
        self.toc_label.pack(anchor=tk.W, padx=5, pady=5)

        # 创建带滚动条的目录树
        toc_tree_frame = tk.Frame(self.toc_frame)
        toc_tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.toc_tree = ttk.Treeview(toc_tree_frame)
        self.toc_tree.heading("#0", text="文档结构")
        toc_scrollbar = tk.Scrollbar(toc_tree_frame, orient=tk.VERTICAL, command=self.toc_tree.yview)
        self.toc_tree.configure(yscrollcommand=toc_scrollbar.set)
        toc_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.toc_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.toc_tree.bind("<<TreeviewSelect>>", self.on_toc_select)

        self.main_paned.add(self.toc_frame)

        # 设置面板初始比例
        self.main_paned.paneconfigure(self.match_frame, minsize=300)
        self.main_paned.paneconfigure(self.content_frame, minsize=600)
        self.main_paned.paneconfigure(self.toc_frame, minsize=300)

        # 底部状态栏
        self.status_bar = tk.Label(
            self.root,
            text="就绪",
            bd=1,
            relief=tk.SUNKEN,
            anchor=tk.W
        )
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # 存储字体大小
        self.current_font_size = 11

        # 快捷键
        self.root.bind("<Alt-1>", lambda e: self.search_tag(self.tags[0]) if len(self.tags) > 0 else None)
        self.root.bind("<Alt-2>", lambda e: self.search_tag(self.tags[1]) if len(self.tags) > 1 else None)
        self.root.bind("<Alt-3>", lambda e: self.search_tag(self.tags[1]) if len(self.tags) > 2 else None)
        self.root.bind("<Alt-4>", lambda e: self.search_tag(self.tags[1]) if len(self.tags) > 3 else None)
        self.root.bind("<Alt-5>", lambda e: self.search_tag(self.tags[1]) if len(self.tags) > 4 else None)

    def create_tag_frame(self):
        # 删除现有标签框架
        if hasattr(self, 'tag_frame_main') and self.tag_frame_main:
            try:
                self.tag_frame_main.destroy()
            except tk.TclError:
                pass

        # 创建主标签框架
        tag_main_frame = tk.Frame(self.root)
        tag_main_frame.pack(fill=tk.X, padx=10, pady=(0, 5))

        # 创建单行布局
        tag_label = tk.Label(tag_main_frame, text="常用搜索:", font=("Arial", 9, "bold"))
        tag_label.pack(side=tk.LEFT, padx=(0, 5))

        # 标签容器框架（使用水平框架而不是Canvas布局）
        self.tag_frame = tk.Frame(tag_main_frame)
        self.tag_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 添加标签按钮放在右侧
        add_tag_button = tk.Button(
            tag_main_frame,
            text="+ 添加标签",
            padx=5,
            relief=tk.GROOVE,
            bg="#e0e0e0",
            activebackground="#d0d0d0",
            cursor="hand2",
            command=self.add_tag_dialog
        )
        add_tag_button.pack(side=tk.RIGHT, padx=5)

        # 创建标签按钮
        self.tag_buttons = []
        if hasattr(self, 'tags'):
            for tag in self.tags:
                self.create_tag_button(tag)

        self.tag_frame_main = tag_main_frame


    def create_tag_button(self, tag_text):
        """Create a button for a single tag with improved styling"""
        # Create a frame to hold the button and close button
        tag_container = tk.Frame(self.tag_frame, bd=1, relief=tk.GROOVE, bg="#e6e6e6")
        tag_container.pack(side=tk.LEFT, padx=3, pady=3)

        # Create the main tag button with better styling
        tag_button = tk.Button(
            tag_container,
            text=tag_text,
            padx=5,
            pady=2,
            relief=tk.FLAT,
            bg="#e6e6e6",
            activebackground="#d0d0d0",
            cursor="hand2",
            command=lambda t=tag_text: self.search_tag(t)
        )
        tag_button.pack(side=tk.LEFT)

        # Create a small close button
        close_button = tk.Button(
            tag_container,
            text="×",
            font=("Arial", 8),
            width=1,
            height=1,
            padx=0,
            pady=0,
            relief=tk.FLAT,
            bg="#e6e6e6",
            activebackground="#ff9999",
            cursor="hand2",
            command=lambda t=tag_text: self.delete_tag(t)
        )
        close_button.pack(side=tk.RIGHT)

        # Bind hover effects for tag button
        tag_button.bind("<Enter>", lambda e: e.widget.config(bg="#d0d0d0"))
        tag_button.bind("<Leave>", lambda e: e.widget.config(bg="#e6e6e6"))

        # Bind hover effects for close button
        close_button.bind("<Enter>", lambda e: e.widget.config(bg="#ff9999", fg="white"))
        close_button.bind("<Leave>", lambda e: e.widget.config(bg="#e6e6e6", fg="black"))

        # Add right-click menu for editing
        tag_menu = tk.Menu(tag_button, tearoff=0)
        tag_menu.add_command(label="编辑标签", command=lambda t=tag_text: self.edit_tag(t))

        # Bind right-click to show menu
        tag_button.bind("<Button-3>", lambda event, menu=tag_menu: menu.post(event.x_root, event.y_root))

        self.tag_buttons.append((tag_container, tag_button, close_button))
        return tag_container
    def search_tag(self, tag_text):
        """Search the knowledge base with the tag text"""
        self.search_var.set(tag_text)
        self.search_knowledge_base(tag_text)

    # Add new method to initialize default tags
    def initialize_default_tags(self):
        """初始化默认标签，当没有已保存的标签时使用"""
        default_tags = [
            "Spring",
            "Spring Boot",
            "MySQL",
            "Mybatis",
            "Cloud",
            "Java",
            "Redis",
            "异常",
            "JVM",
            "并发"
        ]

        # 如果标签列表为空，则加载默认标签
        if not self.tags:
            self.tags = default_tags.copy()
            self.save_tags()  # 保存默认标签
            self.status_bar.config(text="已加载默认搜索标签")

    def add_tag_dialog(self):
        """Show a dialog to add a new tag"""
        dialog = tk.Toplevel(self.root)
        dialog.title("添加新标签")
        dialog.transient(self.root)
        dialog.grab_set()

        # Position the dialog
        dialog.geometry(f"300x120+{self.root.winfo_rootx() + 50}+{self.root.winfo_rooty() + 50}")

        # Entry field for the tag text
        tk.Label(dialog, text="输入标签内容:").pack(pady=(10, 5))
        tag_var = tk.StringVar()
        entry = tk.Entry(dialog, textvariable=tag_var, width=30)
        entry.pack(pady=5, padx=10)
        entry.focus_set()

        # Buttons
        button_frame = tk.Frame(dialog)
        button_frame.pack(pady=10)

        def save_tag():
            tag = tag_var.get().strip()
            if tag and tag not in self.tags:
                self.tags.append(tag)
                self.create_tag_button(tag)
                self.save_tags()
                dialog.destroy()
            elif not tag:
                self.messagebox.showinfo("错误", "标签不能为空")
            else:
                self.messagebox.showinfo("错误", "标签已存在")

        tk.Button(button_frame, text="保存", command=save_tag, width=10).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="取消", command=dialog.destroy, width=10).pack(side=tk.LEFT, padx=5)

        # Enter key to save
        entry.bind('<Return>', lambda e: save_tag())

        # Wait for dialog to close
        self.root.wait_window(dialog)

    def edit_tag(self, old_tag):
        """Show a dialog to edit a tag"""
        dialog = tk.Toplevel(self.root)
        dialog.title("编辑标签")
        dialog.transient(self.root)
        dialog.grab_set()

        dialog.geometry(f"300x120+{self.root.winfo_rootx() + 50}+{self.root.winfo_rooty() + 50}")

        tk.Label(dialog, text="编辑标签内容:").pack(pady=(10, 5))
        tag_var = tk.StringVar(value=old_tag)
        entry = tk.Entry(dialog, textvariable=tag_var, width=30)
        entry.pack(pady=5, padx=10)
        entry.focus_set()

        button_frame = tk.Frame(dialog)
        button_frame.pack(pady=10)

        def update_tag():
            new_tag = tag_var.get().strip()
            if new_tag and (new_tag not in self.tags or new_tag == old_tag):
                # Update tag
                index = self.tags.index(old_tag)
                self.tags[index] = new_tag

                # Recreate tag buttons
                self.create_tag_frame()

                # Save tags
                self.save_tags()
                dialog.destroy()
            elif not new_tag:
                self.messagebox.showinfo("错误", "标签不能为空")
            else:
                self.messagebox.showinfo("错误", "标签已存在")

        tk.Button(button_frame, text="更新", command=update_tag, width=10).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="取消", command=dialog.destroy, width=10).pack(side=tk.LEFT, padx=5)

        entry.bind('<Return>', lambda e: update_tag())

        self.root.wait_window(dialog)

    def delete_tag(self, tag):
        """Delete a tag"""
        if tag in self.tags:
            if self.messagebox.showinfo("确认", f"确定要删除标签 '{tag}' 吗?"):
                self.tags.remove(tag)
                self.create_tag_frame()
                self.save_tags()

    def save_tags(self):
        """Save tags to a file"""
        if self.knowledge_path:
            # Use same base name as knowledge file with .tags extension
            base_name = os.path.splitext(self.knowledge_path)[0]
            tags_file = f"{base_name}.tags"
        else:
            # If no knowledge base loaded, use default
            tags_file = "default.tags"

        try:
            with open(tags_file, 'w', encoding='utf-8') as f:
                for tag in self.tags:
                    f.write(f"{tag}\n")
        except Exception as e:
            print(f"保存标签失败: {str(e)}")
            self.status_bar.config(text=f"保存标签失败: {str(e)}")

    def load_tags(self):
        """Load tags from a file"""
        if self.knowledge_path:
            # Use same base name as knowledge file with .tags extension
            base_name = os.path.splitext(self.knowledge_path)[0]
            tags_file = f"{base_name}.tags"
        else:
            tags_file = "default.tags"
            # return

        # Clear existing tags
        self.tags = []
        tags_loaded = False
        try:
            if os.path.exists(tags_file):
                with open(tags_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        tag = line.strip()
                        if tag:
                            self.tags.append(tag)
                    if self.tags:
                        tags_loaded = True
        except Exception as e:
            print(f"加载标签失败: {str(e)}")
            self.status_bar.config(text=f"加载标签失败: {str(e)}")

        # 如果没有加载到标签，使用默认标签
        if not tags_loaded:
            self.initialize_default_tags()


    def open_knowledge_base(self):
        """打开知识库文件"""
        file_path = filedialog.askopenfilename(
            title="选择知识库文件",
            filetypes=[("Markdown文件", "*.md"), ("文本文件", "*.txt"), ("所有文件", "*.*")]
        )

        if file_path:
            try:
                # 先尝试用UTF-8打开
                try:
                    with open(file_path, 'r', encoding='utf-8') as file:
                        self.knowledge_base = file.read()
                except UnicodeDecodeError:
                    # 如果失败，尝试用GBK打开
                    with open(file_path, 'r', encoding='gbk') as file:
                        self.knowledge_base = file.read()

                self.knowledge_path = file_path

                # 解析知识库
                self.parse_knowledge_base()

                # 构建目录
                self.build_toc()

                # 显示内容
                self.display_knowledge_base()

                # 更新状态
                filename = os.path.basename(file_path)
                self.status_label.config(text=f"状态: 已加载 {filename}")
                self.status_bar.config(text=f"已加载文件: {file_path}")

                # 启用相关功能
                self.file_menu.entryconfig("重新加载", state=tk.NORMAL)

                if SPEECH_AVAILABLE:
                    self.listen_button.config(state=tk.NORMAL)
                    self.process_long_button.config(state=tk.NORMAL)

                # 显示成功信息
                # self.messagebox.showinfo("成功", f"成功加载知识库: {filename}")
                self.status_bar.config(text=f"成功加载知识库: {filename}")

                # 加载与当前知识库关联的标签
                self.load_tags()
                self.create_tag_frame()

            except Exception as e:
                print(f"加载知识库失败: {str(e)}")
                # self.messagebox.showerror("错误", f"加载知识库失败: {str(e)}")
                self.status_bar.config(text=f"错误: {str(e)}")

    def reload_knowledge_base(self):
        """重新加载当前知识库文件"""
        if not self.knowledge_path:
            return


        try:
            # 重新加载文件
            with open(self.knowledge_path, 'r', encoding='utf-8') as file:
                self.knowledge_base = file.read()

            # 刷新显示
            self.parse_knowledge_base()
            self.build_toc()
            self.display_knowledge_base()

            # 更新状态
            filename = os.path.basename(self.knowledge_path)
            self.status_bar.config(text=f"已重新加载文件: {filename}")

            # 重新加载标签
            self.load_tags()
            self.create_tag_frame()

        except Exception as e:
            print(f"重新加载失败: {str(e)}")
            # self.messagebox.showerror("错误", f"重新加载失败: {str(e)}")
            self.status_bar.config(text=f"重新加载错误: {str(e)}")

    def parse_knowledge_base(self):
        """解析知识库，识别标题和内容结构"""
        self.heading_positions = []

        # 判断文件类型
        is_markdown = self.knowledge_path and self.knowledge_path.lower().endswith('.md')

        if is_markdown:
            # Markdown标题模式
            heading_pattern = re.compile(r'^(#{1,6}\s+.+)$', re.MULTILINE)

            for match in heading_pattern.finditer(self.knowledge_base):
                start_pos = match.start()
                heading_text = match.group().strip()

                # 清理Markdown标记
                clean_heading = re.sub(r'^#+\s+', '', heading_text)
                # 获取标题级别
                level = len(re.match(r'^#+', heading_text).group())

                # 存储上下文内容，用于更精确匹配
                context_start = max(0, start_pos - 50)
                context_end = min(len(self.knowledge_base), start_pos + len(heading_text) + 50)
                context = self.knowledge_base[context_start:context_end]

                self.heading_positions.append({
                    'text': clean_heading,
                    'position': start_pos,
                    'raw': heading_text,
                    'level': level,
                    'context': context,  # 添加上下文内容
                    'rendered_position': None  # 将在显示时更新
                })
        else:
            # 文本文件标题识别 (多种格式)

            # 方式1: 下划线式标题 (如 "标题\n====" 或 "标题\n----")
            underline_pattern = re.compile(r'^(.+)\n([=\-]{3,})$', re.MULTILINE)
            for match in underline_pattern.finditer(self.knowledge_base):
                heading_text = match.group(1).strip()
                underline_char = match.group(2)[0]
                level = 1 if underline_char == '=' else 2

                self.heading_positions.append({
                    'text': heading_text,
                    'position': match.start(),
                    'raw': heading_text + '\n' + match.group(2),
                    'level': level
                })

            # 方式2: 数字编号标题 (如 "1. 标题" 或 "1.1 标题")
            number_pattern = re.compile(r'^(\d+\.)+\s+(.+)$', re.MULTILINE)
            for match in number_pattern.finditer(self.knowledge_base):
                heading_text = match.group()
                level = len(re.findall(r'\d+\.', heading_text))

                self.heading_positions.append({
                    'text': heading_text,
                    'position': match.start(),
                    'raw': heading_text,
                    'level': level
                })

            # 方式3: 全大写行或特殊格式行
            if len(self.heading_positions) < 3:  # 如果找到的标题太少
                line_pattern = re.compile(r'^([A-Z\s]{5,})$', re.MULTILINE)
                for match in line_pattern.finditer(self.knowledge_base):
                    heading_text = match.group().strip()

                    self.heading_positions.append({
                        'text': heading_text,
                        'position': match.start(),
                        'raw': heading_text,
                        'level': 1
                    })

        # 按位置排序
        self.heading_positions.sort(key=lambda x: x['position'])

    def manual_search(self):
        """手动触发搜索"""
        query = self.search_var.get().strip()
        if not query:
            print("请输入搜索关键词")
            # self.messagebox.showinfo("提示", "请输入搜索关键词")
            self.status_bar.config(text=f"提示：请输入搜索关键词")

            return

        if not self.knowledge_base:
            print("请先加载知识库")
            # self.messagebox.showinfo("提示", "请先加载知识库")
            self.status_bar.config(text=f"提示：请先加载知识库")
            return

        # 执行搜索
        self.search_knowledge_base(query)

        # 如果搜索成功且关键词不在标签中，提示添加到常用标签
        try:
            if query and self.knowledge_base and query not in self.tags and len(self.current_matches) > 0:
                if len(self.tags) < 10:  # 限制标签数量，避免过多
                    result = messagebox.askyesno("添加标签",f"是否将\"{query}\"添加到常用搜索标签？",parent = self.root)
                    if result:
                        self.tags.append(query)
                        self.create_tag_frame()
                        self.save_tags()
                        self.status_bar.config(text=f"已添加\"{query}\"到常用搜索标签")
                elif len(self.tags) >= 10:
                    # 如果标签数量达到上限，提示用户删除一些标签
                    self.status_bar.config(text="标签数量已达上限(10个)，请删除一些标签再添加新标签")
        except Exception as e:
            print(f"添加标签时出错: {str(e)}")
            self.status_bar.config(text=f"添加标签时出错: {str(e)}")

    def clear_search(self):
        """清除搜索框和结果"""
        self.search_var.set("")
        self.match_list.delete(0, tk.END)

        # 清除文本中的高亮
        self.content_text.tag_remove("search_highlight", "1.0", tk.END)

        # 清除文本历史
        self.text_history = []

        # 更新状态
        self.status_bar.config(text="搜索已清除")

    def highlight_search_matches(self, query, matches):
        """在文本中高亮显示搜索匹配项"""
        # 清除之前的高亮
        self.content_text.tag_remove("search_highlight", "1.0", tk.END)

        # 如果没有查询或者没有匹配项，就直接返回
        if not query or not matches:
            return

        # 提取关键词
        keywords = self.extract_keywords(query)

        # 为关键词创建正则表达式
        patterns = []
        for keyword in keywords:
            # 转义特殊字符
            escaped_keyword = re.escape(keyword)
            # 添加匹配模式
            patterns.append(escaped_keyword)

        # 如果没有有效的模式，直接返回
        if not patterns:
            return

        # 创建合并的模式
        pattern_str = '|'.join(patterns)
        try:
            pattern = re.compile(pattern_str, re.IGNORECASE)
        except:
            # 如果正则表达式编译失败，则返回
            return

        # 在整个文本中查找匹配项
        text_content = self.knowledge_base
        for match in pattern.finditer(text_content):
            start_pos = match.start()
            end_pos = match.end()

            # 转换字符位置为行列位置
            start_line = text_content.count('\n', 0, start_pos) + 1
            start_col = start_pos - text_content.rfind('\n', 0, start_pos) - 1
            if start_col < 0:
                start_col = 0

            end_line = text_content.count('\n', 0, end_pos) + 1
            end_col = end_pos - text_content.rfind('\n', 0, end_pos) - 1
            if end_col < 0:
                end_col = 0

            # 添加高亮标记
            try:
                self.content_text.tag_add(
                    "search_highlight",
                    f"{start_line}.{start_col}",
                    f"{end_line}.{end_col}"
                )
            except:
                # 如果标记添加失败，跳过此匹配项
                continue

        # 配置高亮标记的样式
        self.content_text.tag_config("search_highlight", background="#FFFF66", foreground="#000000")

    # def setup_autocomplete(self):
    #     """为搜索框设置自动完成功能"""
    #
    #     # 创建下拉列表窗口
    #     self.ac_listbox = None
    #
    #     def show_autocomplete_dropdown(suggestions):
    #         """显示自动完成下拉菜单"""
    #         if not suggestions:
    #             if self.ac_listbox:
    #                 self.ac_listbox.destroy()
    #                 self.ac_listbox = None
    #             return
    #
    #         # 获取搜索框位置
    #         x = self.search_entry.winfo_rootx()
    #         y = self.search_entry.winfo_rooty() + self.search_entry.winfo_height()
    #
    #         # 创建下拉框
    #         if not self.ac_listbox:
    #             self.ac_listbox = tk.Toplevel(self.root)
    #             self.ac_listbox.overrideredirect(True)  # 无边框窗口
    #             self.ac_listbox.geometry(f"+{x}+{y}")
    #
    #             listbox = tk.Listbox(self.ac_listbox, width=self.search_entry.winfo_width())
    #             listbox.pack(fill=tk.BOTH, expand=True)
    #
    #             # 点击选择
    #             listbox.bind("<ButtonRelease-1>", on_select_suggestion)
    #             # 按回车选择
    #             listbox.bind("<Return>", on_select_suggestion)
    #         else:
    #             self.ac_listbox.geometry(f"+{x}+{y}")
    #             listbox = self.ac_listbox.winfo_children()[0]
    #             listbox.delete(0, tk.END)
    #
    #         # 添加建议项
    #         for suggestion in suggestions:
    #             listbox.insert(tk.END, suggestion)
    #
    #     def on_select_suggestion(event):
    #         """当选择一个建议项时"""
    #         if self.ac_listbox:
    #             listbox = self.ac_listbox.winfo_children()[0]
    #             selection = listbox.curselection()
    #             if selection:
    #                 selected_text = listbox.get(selection[0])
    #                 self.search_var.set(selected_text)
    #                 self.ac_listbox.destroy()
    #                 self.ac_listbox = None
    #                 # 可选：立即执行搜索
    #                 self.manual_search()
    #
    #     def update_suggestions(event):
    #         """键入时更新建议"""
    #         current_text = self.search_var.get().lower()
    #         if len(current_text) >= 2:  # 至少输入2个字符才显示建议
    #             suggestions = [tag for tag in self.tags if current_text in tag.lower()]
    #             show_autocomplete_dropdown(suggestions[:10])  # 限制显示数量
    #         elif self.ac_listbox:
    #             self.ac_listbox.destroy()
    #             self.ac_listbox = None
    #
    #     # 当输入文字时触发建议
    #     self.search_entry.bind("<KeyRelease>", update_suggestions)
    #
    #     # 点击其他地方或ESC键关闭下拉框
    #     self.root.bind("<Button-1>", lambda e: self.ac_listbox.destroy() if self.ac_listbox else None)
    #     self.root.bind("<Escape>", lambda e: self.ac_listbox.destroy() if self.ac_listbox else None)
    #
    #     # 焦点离开搜索框时关闭建议
    #     self.search_entry.bind("<FocusOut>", lambda e:
    #     self.root.after(100, lambda: self.ac_listbox.destroy() if self.ac_listbox else None))
    #
    # # 增强版：加入搜索历史
    # def setup_enhanced_autocomplete(self):
    #     # 初始化搜索历史记录
    #     self.search_history = self.load_search_history()
    #
    #     # 同时显示标签和历史记录
    #     def get_suggestions(text):
    #         tag_suggestions = [f"🏷️ {tag}" for tag in self.tags
    #                            if text.lower() in tag.lower()]
    #
    #         history_suggestions = [f"🕒 {hist}" for hist in self.search_history
    #                                if text.lower() in hist.lower()]
    #
    #         # 按相关度排序（完全匹配 > 起始匹配 > 包含匹配）
    #         def get_relevance(item):
    #             item_text = item[2:]  # 移除前缀
    #             if item_text.lower() == text.lower():
    #                 return 0
    #             elif item_text.lower().startswith(text.lower()):
    #                 return 1
    #             else:
    #                 return 2
    #
    #         all_suggestions = sorted(tag_suggestions + history_suggestions[:5],
    #                                  key=get_relevance)
    #         return all_suggestions[:10]
    #
    #     # 修改update_suggestions函数以使用get_suggestions
    #
    #     # 添加历史记录保存函数
    #     def add_to_search_history(query):
    #         if query and query not in self.search_history:
    #             self.search_history.insert(0, query)
    #             self.search_history = self.search_history[:20]  # 限制历史记录数量
    #             self.save_search_history()


    def build_toc(self):
        """根据解析的标题构建目录树"""
        # 清空现有项目
        for item in self.toc_tree.get_children():
            self.toc_tree.delete(item)

        # 跟踪不同标题级别的父节点
        parents = {0: ''}  # 根级别
        last_item_at_level = {}

        # 添加每个标题到树中
        for i, heading in enumerate(self.heading_positions):
            level = heading['level']
            text = heading['text']

            # 找到此标题的父节点
            parent_level = 0
            for l in sorted(parents.keys(), reverse=True):
                if l < level:
                    parent_level = l
                    break
            parent = parents[parent_level]

            # 添加标题到树中
            item_id = self.toc_tree.insert(
                parent,
                'end',
                text=text,
                values=(heading['position'],)
            )

            # 更新父节点记录
            parents[level] = item_id
            last_item_at_level[level] = item_id

            # 删除任何更深级别的父节点（因为它们不再有效）
            keys_to_remove = [k for k in parents.keys() if k > level]
            for k in keys_to_remove:
                parents.pop(k, None)

        # 初始展开所有一级项目
        for item in self.toc_tree.get_children():
            self.toc_tree.item(item, open=True)

    def render_markdown(self, markdown_text):
        """渲染Markdown文本到富文本显示"""
        # 配置标签样式
        self.content_text.tag_configure("h1", font=("Arial", 18, "bold"), foreground="#0066CC", spacing3=5)
        self.content_text.tag_configure("h2", font=("Arial", 16, "bold"), foreground="#0099CC", spacing3=4)
        self.content_text.tag_configure("h3", font=("Arial", 14, "bold"), foreground="#33CCCC", spacing3=3)
        self.content_text.tag_configure("h4", font=("Arial", 12, "bold"), spacing3=2)
        self.content_text.tag_configure("bold", font=("Courier New", self.current_font_size, "bold"))
        self.content_text.tag_configure("italic", font=("Courier New", self.current_font_size, "italic"))
        self.content_text.tag_configure("code", font=("Consolas", self.current_font_size), background="#f0f0f0")
        self.content_text.tag_configure("code_block", font=("Consolas", self.current_font_size), background="#f0f0f0",
                                        spacing1=5, spacing3=5, relief=tk.GROOVE, borderwidth=1)
        self.content_text.tag_configure("bullet", lmargin1=20, lmargin2=30)
        self.content_text.tag_configure("link", foreground="blue", underline=1)

        # 按行处理Markdown
        lines = markdown_text.split('\n')
        in_code_block = False
        code_block_content = []

        i = 0
        while i < len(lines):
            line = lines[i]

            # 处理代码块
            if line.strip().startswith('```'):
                if in_code_block:
                    # 结束代码块
                    code_text = '\n'.join(code_block_content)
                    self.content_text.insert(tk.END, code_text, "code_block")
                    self.content_text.insert(tk.END, "\n\n")
                    code_block_content = []
                    in_code_block = False
                else:
                    # 开始代码块
                    in_code_block = True
                i += 1
                continue

            if in_code_block:
                code_block_content.append(line)
                i += 1
                continue

            # 处理标题
            if line.startswith('# '):
                self.content_text.insert(tk.END, line[2:], "h1")
                self.content_text.insert(tk.END, "\n\n")
            elif line.startswith('## '):
                self.content_text.insert(tk.END, line[3:], "h2")
                self.content_text.insert(tk.END, "\n\n")
            elif line.startswith('### '):
                self.content_text.insert(tk.END, line[4:], "h3")
                self.content_text.insert(tk.END, "\n\n")
            elif line.startswith('#### '):
                self.content_text.insert(tk.END, line[5:], "h4")
                self.content_text.insert(tk.END, "\n\n")
            # 处理列表项
            elif line.strip().startswith('- ') or line.strip().startswith('* '):
                self.content_text.insert(tk.END, "• " + line.strip()[2:], "bullet")
                self.content_text.insert(tk.END, "\n")
            # 处理普通段落
            else:
                # 处理行内格式
                processed_line = line

                # 插入处理后的行
                if line.strip():
                    self.process_inline_markdown(processed_line)
                else:
                    # 空行
                    self.content_text.insert(tk.END, "\n")

            i += 1

    def process_inline_markdown(self, line):
        """处理行内Markdown格式"""
        # 初始位置
        current_pos = 0
        result = ""

        # 解析行内格式
        i = 0
        while i < len(line):
            # 检查加粗 (**text**)
            if i + 1 < len(line) and line[i:i + 2] == '**':
                # 先插入普通文本
                if i > current_pos:
                    self.content_text.insert(tk.END, line[current_pos:i])

                # 寻找结束标记
                end = line.find('**', i + 2)
                if end != -1:
                    # 提取加粗文本并应用tag
                    bold_text = line[i + 2:end]
                    self.content_text.insert(tk.END, bold_text, "bold")

                    # 更新位置
                    i = end + 2
                    current_pos = i
                    continue

            # 检查斜体 (*text*)
            elif line[i] == '*' and (i == 0 or line[i - 1] != '*') and (i + 1 < len(line) and line[i + 1] != '*'):
                # 先插入普通文本
                if i > current_pos:
                    self.content_text.insert(tk.END, line[current_pos:i])

                # 寻找结束标记
                end = line.find('*', i + 1)
                if end != -1:
                    # 提取斜体文本并应用tag
                    italic_text = line[i + 1:end]
                    self.content_text.insert(tk.END, italic_text, "italic")

                    # 更新位置
                    i = end + 1
                    current_pos = i
                    continue

            # 检查行内代码 (`code`)
            elif line[i] == '`':
                # 先插入普通文本
                if i > current_pos:
                    self.content_text.insert(tk.END, line[current_pos:i])

                # 寻找结束标记
                end = line.find('`', i + 1)
                if end != -1:
                    # 提取代码文本并应用tag
                    code_text = line[i + 1:end]
                    self.content_text.insert(tk.END, code_text, "code")

                    # 更新位置
                    i = end + 1
                    current_pos = i
                    continue

            i += 1

        # 插入剩余文本
        if current_pos < len(line):
            self.content_text.insert(tk.END, line[current_pos:])

        # 添加换行
        self.content_text.insert(tk.END, "\n")
    def find_all_pairs(self, text, start_marker, end_marker):
        """找出所有成对的标记"""
        result = []
        pos = 0

        while True:
            start = text.find(start_marker, pos)
            if start == -1:
                break

            end = text.find(end_marker, start + len(start_marker))
            if end == -1:
                break

            result.append((start, end + len(end_marker)))
            pos = end + len(end_marker)

        return result


    def display_knowledge_base(self):
        """在界面中显示知识库内容，支持Markdown渲染"""
        # 启用文本区域进行编辑
        self.content_text.config(state=tk.NORMAL)
        self.content_text.delete(1.0, tk.END)

        # 检查是否为Markdown文件
        is_markdown = self.knowledge_path and self.knowledge_path.lower().endswith('.md')

        # 创建位置映射字典，用于存储原始位置到渲染后位置的映射
        self.position_mapping = {}

        if is_markdown:
            # 使用Markdown渲染器显示
            self.render_markdown(self.knowledge_base)

            # 记录渲染后的所有标题位置，用于目录导航
            # (由于标签的存在，原始字符位置可能无法直接使用)
            for heading in self.heading_positions:
                # 在渲染后的文本中找到对应标题
                search_text = heading['text']
                start_idx = "1.0"
                while True:
                    pos = self.content_text.search(search_text, start_idx, stopindex=tk.END)
                    if not pos:
                        break

                    # 验证这确实是标题而不是内容中相同的文本
                    # 检查周围文本或标签来确认
                    line_start = pos.split('.')[0]
                    if self.content_text.tag_names(pos):
                        tags = self.content_text.tag_names(pos)
                        # 如果有一个标题标签，这可能是正确的位置
                        if any(tag.startswith('h') for tag in tags):
                            heading['rendered_position'] = pos
                            self.position_mapping[heading['position']] = pos
                            break

                    # 尝试下一个匹配
                    start_idx = self.content_text.index(f"{pos}+1c")
        else:
            # 非Markdown文件使用原有展示方式
            self.content_text.insert(tk.END, self.knowledge_base)

            # 高亮显示所有标题
            for heading in self.heading_positions:
                position = heading['position']
                # 将字符位置转换为行列位置
                line_start = self.knowledge_base.count('\n', 0, position) + 1
                col_start = position - self.knowledge_base.rfind('\n', 0, position) - 1
                if col_start < 0:
                    col_start = 0

                # 计算标题的结束位置
                raw_heading = heading['raw']
                line_end = line_start + raw_heading.count('\n')

                if line_start == line_end:
                    col_end = col_start + len(raw_heading)
                    start_pos = f"{line_start}.{col_start}"
                    end_pos = f"{line_end}.{col_end}"
                else:
                    # 多行标题的情况
                    last_line_length = len(raw_heading.split('\n')[-1])
                    start_pos = f"{line_start}.{col_start}"
                    end_pos = f"{line_end}.{last_line_length}"

                # 根据标题级别设置不同的颜色
                level = heading.get('level', 1)

                # 标记标题文本
                self.content_text.tag_add(f"heading_{position}", start_pos, end_pos)

                # 根据标题级别设置字体大小和颜色
                font_size = max(self.current_font_size, self.current_font_size + 5 - level)  # 一级标题最大，依次递减
                if level == 1:
                    color = "#0066CC"  # 深蓝色
                elif level == 2:
                    color = "#0099CC"  # 中蓝色
                else:
                    color = "#33CCCC"  # 浅蓝色

                self.content_text.tag_config(
                    f"heading_{position}",
                    foreground=color,
                    font=("Courier New", font_size, "bold")
                )

        # 禁用文本区域，防止编辑
        self.content_text.config(state=tk.DISABLED)
    def change_speech_engine(self):
        """更改语音识别引擎"""
        if not SPEECH_AVAILABLE:
            print("语音识别功能不可用。请安装speech_recognition模块")
            # self.messagebox.showwarning("功能不可用", "语音识别功能不可用。请安装speech_recognition模块")
            self.status_bar.config(text=f"语音识别功能不可用。请安装speech_recognition模块")
            return

        new_engine = self.engine_var.get()
        self.speech_engine = new_engine

        if self.speech_engine == "Vosk" and not self.vosk_model and VOSK_AVAILABLE:
            # self.messagebox.showinfo("提示", "请先下载Vosk模型，或者切换到其他语音引擎。")
            self.status_bar.config(text=f"请先下载Vosk模型，或者切换到其他语音引擎。")


        # self.messagebox.showinfo("语音引擎已更改", f"已切换到 {new_engine} 语音识别引擎")
        self.status_bar.config(text=f"语音引擎已更改：已切换到 {new_engine} 语音识别引擎")

    def download_vosk_model(self):
        """提供Vosk模型下载指南"""
        if not VOSK_AVAILABLE:
            print("Vosk功能不可用。请安装vosk模块")
            # self.messagebox.showwarning("功能不可用", "Vosk功能不可用。请安装vosk模块")
            self.status_bar.config(text=f"功能不可用：Vosk功能不可用。请安装vosk模块")
            return

        guide = """
要使用Vosk离线语音识别，请按照以下步骤下载语音模型:

1. 访问 https://alphacephei.com/vosk/models
2. 下载中文小型模型 (vosk-model-small-cn-0.22)
3. 解压下载的文件
4. 创建一个名为 'models' 的文件夹在程序目录下
5. 将解压后的模型文件夹放入 'models' 文件夹中
6. 重启本程序

提示: 模型大小约为40MB，下载后需要解压。
        """
        self.messagebox.showinfo("Vosk模型下载指南", guide)


    def show_sensitivity_dialog(self):
        """显示模糊匹配灵敏度调整对话框"""
        sensitivity_dialog = tk.Toplevel(self.root)
        sensitivity_dialog.title("模糊匹配灵敏度")
        sensitivity_dialog.geometry("400x200")
        sensitivity_dialog.transient(self.root)
        sensitivity_dialog.grab_set()

        # 创建说明标签
        explanation = "调整模糊匹配的灵敏度：较低的值会匹配更多内容但准确性降低，较高的值需要更精确的匹配"
        label = tk.Label(sensitivity_dialog, text=explanation, wraplength=380, justify=tk.LEFT)
        label.pack(pady=15, padx=10)

        # 创建滑块
        slider_label = tk.Label(sensitivity_dialog, text=f"灵敏度 ({self.fuzzy_ratio}%):")
        slider_label.pack(pady=5)

        slider_var = tk.IntVar(value=self.fuzzy_ratio)

        def update_slider_label(value):
            slider_label.config(text=f"灵敏度 ({value}%):")

        slider = tk.Scale(
            sensitivity_dialog,
            from_=50,
            to=100,
            orient=tk.HORIZONTAL,
            length=300,
            variable=slider_var,
            command=update_slider_label
        )
        slider.pack(pady=5)

        # 按钮框架
        button_frame = tk.Frame(sensitivity_dialog)
        button_frame.pack(pady=15)

        def save_setting():
            self.fuzzy_ratio = slider_var.get()
            sensitivity_dialog.destroy()

            # 如果已经进行过搜索，应用新设置重新搜索
            if hasattr(self, 'last_search_query') and self.last_search_query:
                self.search_knowledge_base(self.last_search_query)

        save_button = tk.Button(
            button_frame,
            text="保存",
            command=save_setting,
            width=10,
            height=1
        )
        save_button.pack(side=tk.LEFT, padx=10)

        cancel_button = tk.Button(
            button_frame,
            text="取消",
            command=sensitivity_dialog.destroy,
            width=10,
            height=1
        )
        cancel_button.pack(side=tk.LEFT, padx=10)

    def increase_font_size(self):
        """增加文本区域字体大小"""
        if self.current_font_size < 24:  # 最大字体限制
            self.current_font_size += 1
            self.content_text.config(font=("Courier New", self.current_font_size))

            # 刷新标题样式
            if self.knowledge_base:
                self.display_knowledge_base()

            self.status_bar.config(text=f"字体大小: {self.current_font_size}")

#  第二段
    def decrease_font_size(self):
        """减小文本区域字体大小"""
        if self.current_font_size > 8:  # 最小字体限制
            self.current_font_size -= 1
            self.content_text.config(font=("Courier New", self.current_font_size))

            # 刷新标题样式
            if self.knowledge_base:
                self.display_knowledge_base()

            self.status_bar.config(text=f"字体大小: {self.current_font_size}")

    def expand_all_toc(self, expand):
        """展开或折叠所有目录项"""
        for item in self.toc_tree.get_children():
            self.expand_item_recursive(item, expand)

        status = "展开" if expand else "折叠"
        self.status_bar.config(text=f"已{status}所有目录项")

    def expand_item_recursive(self, item, expand):
        """递归展开或折叠目录项及其子项"""
        children = self.toc_tree.get_children(item)
        if children:
            if expand:
                self.toc_tree.item(item, open=True)
            else:
                self.toc_tree.item(item, open=False)

            for child in children:
                self.expand_item_recursive(child, expand)

    def toggle_listening(self):
        """切换语音监听状态"""
        if not SPEECH_AVAILABLE:
            print("语音识别功能不可用。请安装speech_recognition模块")
            # self.messagebox.showwarning("功能不可用", "语音识别功能不可用。请安装speech_recognition模块")
            self.status_bar.config(text=f"功能不可用：语音识别功能不可用。请安装speech_recognition模块")

            return

        if not self.knowledge_path:
            print("请先加载知识库文件")
            # self.messagebox.showwarning("警告", "请先加载知识库文件")
            self.status_bar.config(text=f"警告：请先加载知识库文件")
            return

        if self.listening:
            # 停止监听
            self.listening = False
            self.listen_button.config(text="开始监听", bg="green")
            self.status_bar.config(text="语音监听: 关闭")
        else:
            # 开始监听
            self.listening = True
            self.listen_button.config(text="停止监听", bg="red")
            self.status_bar.config(text="语音监听: 开启")

            # 在新线程中启动语音识别
            threading.Thread(target=self.start_listening, daemon=True).start()

    def start_listening(self):
        """启动语音识别线程"""
        if not SPEECH_AVAILABLE:
            self.status_bar.config(text="语音识别库未安装，请安装speech_recognition模块")
            return

        # 检查选择的引擎
        engine = self.speech_engine
        print(f"Using engine: {engine}")  # 调试信息

        # Vosk引擎需要特殊处理
        if engine == "Vosk" and VOSK_AVAILABLE:
            self.start_vosk_listening()
            return

        try:
            with self.mic as source:
                # 调整麦克风噪声水平
                print("Adjusting for ambient noise...")
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                print("Adjustment complete")
        except Exception as e:
            print(f"麦克风初始化错误: {e}")
            self.status_bar.config(text=f"麦克风初始化错误: {e}")
            self.listening = False
            self.listen_button.config(text="开始监听", bg="green")
            return

        while self.listening:
            try:
                with self.mic as source:
                    self.status_bar.config(text="语音监听: 正在听...")
                    print("Listening... Energy threshold:", self.recognizer.energy_threshold)
                    # 增加短语时间限制，适应更长的句子
                    # audio = self.recognizer.listen(source, timeout=3, phrase_time_limit=5)
                    audio = self.recognizer.listen(source, timeout=5)  # 延长等待时间，移除短语时间限制
                    print("Got audio! Duration approximately:", len(audio.frame_data) / 16000, "seconds")

                    # 添加到音频缓冲区用于长对话处理
                    self.audio_buffer.append(audio)
                    if len(self.audio_buffer) > self.max_buffer_size:
                        self.audio_buffer.pop(0)  # 如果缓冲区满了，移除最旧的片段

                self.status_bar.config(text="语音监听: 正在处理...")
                print("Processing audio...")

                # 根据选择的引擎进行识别
                if engine == "Google":
                    text = self.recognizer.recognize_google(audio, language='zh-CN')
                elif engine == "Sphinx":
                    text = self.recognizer.recognize_sphinx(audio, language='zh-cn')
                else:
                    # 默认回退到Google
                    text = self.recognizer.recognize_google(audio, language='zh-CN')

                print(f"Recognized: {text}")

                # 添加到文本历史
                self.text_history.append(text)
                if len(self.text_history) > 5:  # 保留最近5个短语
                    self.text_history.pop(0)

                # 更新搜索框
                self.search_var.set(text)

                # 在主线程中执行搜索
                self.root.after(0, self.search_knowledge_base, text)

            except sr.WaitTimeoutError:
                print("Wait timeout")
                self.status_bar.config(text="语音监听: 等待输入...")
                continue
            except sr.UnknownValueError:
                print("Unknown value")
                self.status_bar.config(text="语音监听: 未能识别，请再说一遍...")
                continue
            except sr.RequestError as e:
                print(f"Request error: {e}")
                self.status_bar.config(text=f"语音监听错误: {e}")
                if "Google" in engine:
                    # 如果Google识别出错，提示可以切换到离线引擎
                    self.status_bar.config(text="语音识别错误：无法连接到Google服务。建议切换到离线引擎。")
                self.toggle_listening()  # 停止监听
                break
            except Exception as e:
                print(f"Error: {type(e).__name__}: {e}")
                self.status_bar.config(text=f"语音监听错误: {e}")
                time.sleep(0.5)  # 短暂暂停防止循环过快
                continue

    def start_vosk_listening(self):
            """使用Vosk离线引擎进行语音识别"""
            if not VOSK_AVAILABLE:
                print("Vosk语音识别功能不可用。请安装vosk模块")
                self.status_bar.config(text="Vosk语音识别功能不可用。请安装vosk模块")
                return

            # 检查模型
            model_path = os.path.join("models", "vosk-model-small-cn-0.22")
            print(f"检查Vosk模型路径: {model_path}")

            if not self.vosk_model:
                # 尝试加载模型
                if os.path.exists(model_path):
                    try:
                        print("正在加载Vosk模型...")
                        self.vosk_model = Model(model_path)
                        print("Vosk模型加载成功")
                        self.status_bar.config(text="Vosk模型加载成功")
                    except Exception as e:
                        print(f"加载Vosk模型失败: {str(e)}")
                        self.status_bar.config(text=f"加载Vosk模型失败: {str(e)}")
                        self.messagebox.showerror("错误", f"加载Vosk模型失败: {str(e)}")
                        self.toggle_listening()
                        return
                else:
                    print(f"Vosk模型未找到，路径: {model_path}")
                    self.status_bar.config(text="Vosk模型未找到。请下载模型或切换到其他引擎。")
                    self.messagebox.showwarning("警告", "Vosk模型未找到。请下载模型或切换到其他引擎。")
                    self.toggle_listening()
                    return

            # 创建识别器
            try:
                print("创建Vosk识别器...")
                recognizer = KaldiRecognizer(self.vosk_model, 16000)
                print("Vosk识别器创建成功")
            except Exception as e:
                print(f"创建Vosk识别器失败: {str(e)}")
                self.status_bar.config(text=f"创建Vosk识别器失败: {str(e)}")
                self.toggle_listening()
                return

            try:
                print("正在初始化PyAudio...")
                import pyaudio
                p = pyaudio.PyAudio()

                # 检查可用设备
                info = p.get_host_api_info_by_index(0)
                num_devices = info.get('deviceCount')
                print(f"发现 {num_devices} 个音频设备")

                for i in range(0, num_devices):
                    if (p.get_device_info_by_host_api_device_index(0, i).get('maxInputChannels')) > 0:
                        print(f"输入设备 {i}: {p.get_device_info_by_host_api_device_index(0, i).get('name')}")

                print("正在打开音频流...")
                stream = p.open(format=pyaudio.paInt16,
                                channels=1,
                                rate=16000,
                                input=True,
                                frames_per_buffer=8000)
                stream.start_stream()
                print("音频流开启成功")

                while self.listening:
                    try:
                        self.status_bar.config(text="语音监听: 正在听(Vosk)...")
                        data = stream.read(4000, exception_on_overflow=False)

                        if recognizer.AcceptWaveform(data):
                            result = json.loads(recognizer.Result())
                            text = result.get("text", "")

                            if text:
                                print(f"Vosk识别结果: '{text}'")
                                # 添加到文本历史
                                self.text_history.append(text)
                                if len(self.text_history) > 5:
                                    self.text_history.pop(0)

                                # 更新搜索框
                                self.search_var.set(text)

                                # 在主线程中执行搜索
                                self.root.after(0, self.search_knowledge_base, text)

                    except Exception as e:
                        print(f"Vosk处理错误: {type(e).__name__}: {str(e)}")
                        self.status_bar.config(text=f"Vosk错误: {str(e)}")
                        time.sleep(0.5)

                # 停止并关闭流
                print("正在关闭音频流...")
                stream.stop_stream()
                stream.close()
                p.terminate()
                print("音频流已关闭")

            except Exception as e:
                print(f"初始化PyAudio详细错误: {type(e).__name__}: {str(e)}")
                self.status_bar.config(text=f"初始化PyAudio失败: {str(e)}")
                self.messagebox.showerror("错误", f"初始化PyAudio失败: {str(e)}")
                self.toggle_listening()

    def diagnose_speech_recognition(self):
        """诊断语音识别功能"""
        diagnosis = "语音识别诊断结果:\n\n"

        # 检查依赖库
        diagnosis += "1. 依赖库检查:\n"
        diagnosis += f"   - speech_recognition: {'已安装' if SPEECH_AVAILABLE else '未安装'}\n"
        diagnosis += f"   - vosk: {'已安装' if VOSK_AVAILABLE else '未安装'}\n"
        diagnosis += f"   - pyaudio: {'已安装' if 'pyaudio' in sys.modules else '未安装'}\n\n"

        # 检查语音引擎
        diagnosis += "2. 语音引擎设置:\n"
        diagnosis += f"   - 当前引擎: {self.speech_engine}\n"

        # 检查麦克风
        diagnosis += "\n3. 麦克风检查:\n"
        if SPEECH_AVAILABLE:
            try:
                with self.mic as source:
                    diagnosis += "   - 麦克风初始化: 成功\n"
                    try:
                        self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                        diagnosis += "   - 麦克风噪声调整: 成功\n"
                    except Exception as e:
                        diagnosis += f"   - 麦克风噪声调整: 失败 ({str(e)})\n"
            except Exception as e:
                diagnosis += f"   - 麦克风初始化: 失败 ({str(e)})\n"
        else:
            diagnosis += "   - 无法检查麦克风，speech_recognition未安装\n"

        # Vosk模型检查
        diagnosis += "\n4. Vosk模型检查:\n"
        if VOSK_AVAILABLE:
            model_path = os.path.join("models", "vosk-model-small-cn-0.22")
            if os.path.exists(model_path):
                diagnosis += f"   - 模型路径 '{model_path}': 存在\n"
                # 检查模型内容
                if os.path.isdir(model_path):
                    model_files = os.listdir(model_path)
                    if 'am' in model_files and 'conf' in model_files:
                        diagnosis += "   - 模型文件: 完整\n"
                    else:
                        diagnosis += f"   - 模型文件: 不完整，缺少必要文件，现有: {', '.join(model_files)}\n"
                else:
                    diagnosis += "   - 模型路径存在，但不是目录\n"
            else:
                diagnosis += f"   - 模型路径 '{model_path}': 不存在\n"
        else:
            diagnosis += "   - 无法检查Vosk模型，vosk未安装\n"

        # 显示诊断结果
        print(diagnosis)
        self.messagebox.showinfo("语音识别诊断", diagnosis)

        # 添加到状态栏
        if SPEECH_AVAILABLE:
            if 'pyaudio' in sys.modules:
                self.status_bar.config(text="诊断完成: 基础依赖库已安装")
            else:
                self.status_bar.config(text="诊断完成: 请安装pyaudio库")
        else:
            self.status_bar.config(text="诊断完成: 请安装speech_recognition库")
    def process_long_conversation(self):
        """处理累积的音频缓冲区用于长对话"""
        if not self.audio_buffer and not self.text_history:
            print("没有可用的语音数据。请先进行一些语音输入。")
            # self.messagebox.showinfo("提示", "没有可用的语音数据。请先进行一些语音输入。")
            self.status_bar.config(text=f"提示：没有可用的语音数据。请先进行一些语音输入。")
            return

        # 合并现有文本历史
        if self.text_history:
            combined_text = " ".join(self.text_history)
            self.search_var.set(combined_text)
            self.search_knowledge_base(combined_text)
            # self.messagebox.showinfo("处理完成", f"已处理长对话并搜索关键词:\n\n{combined_text}")
            self.status_bar.config(text=f"处理完成：已处理长对话并搜索关键词：{combined_text}")
        else:
            print("没有识别到完整的语音内容")
            # self.messagebox.showinfo("提示", "没有识别到完整的语音内容")
            self.status_bar.config(text=f"提示：没有识别到完整的语音内容")


    def extract_keywords(self, text):
            """从文本中提取重要关键词，支持中英文"""
            keywords = []

            # 对于中文文本，使用jieba分词（如果可用）
            chinese_text = any('\u4e00' <= char <= '\u9fff' for char in text)
            if chinese_text and JIEBA_AVAILABLE:
                words = jieba.cut(text)
                # 过滤掉常见词和短词
                keywords = [word for word in words if len(word) >= 2 and not word.isdigit()]

            # 对于英文和混合文本
            if NLTK_AVAILABLE:
                # 使用NLTK处理英文
                try:
                    stop_words = set(stopwords.words('english'))
                    words = word_tokenize(text)
                    eng_keywords = [word.lower() for word in words
                                    if word.isalnum() and len(word) > 2
                                    and word.lower() not in stop_words]
                    keywords.extend(eng_keywords)
                except:
                    # 如果NLTK失败，回退到简单方法
                    eng_words = re.findall(r'\b[a-zA-Z]{3,}\b', text)
                    keywords.extend([word.lower() for word in eng_words])
            else:
                # 不使用NLTK的简单方法
                eng_words = re.findall(r'\b[a-zA-Z]{3,}\b', text)
                keywords.extend([word.lower() for word in eng_words])

            # 提取技术术语和特殊格式词
            tech_terms = re.findall(r'\b[a-zA-Z0-9]+(?:[._-][a-zA-Z0-9]+)*\b', text)
            tech_terms = [term for term in tech_terms if len(term) > 3 and ('.' in term or '_' in term or '-' in term)]
            keywords.extend(tech_terms)

            # 如果没有找到任何关键词，使用原始查询
            if not keywords and len(text) < 50:
                keywords.append(text)

            # 去除重复项
            return list(set(keywords))

    def search_knowledge_base(self, query):
        """在知识库中搜索关键词，支持模糊匹配"""
        # 保存最近的搜索查询
        self.last_search_query = query

        # 清空匹配列表
        self.match_list.delete(0, tk.END)

        if not query or not self.knowledge_base:
            return

        # 从查询中提取关键词
        keywords = self.extract_keywords(query)

        # 搜索结果
        matches = []

        # 检查是否启用模糊匹配
        use_fuzzy = self.fuzzy_match_var.get()

        # 使用当前设置的模糊匹配阈值
        fuzzy_threshold = self.fuzzy_ratio

        # 首先在标题中搜索（优先匹配标题）
        for heading in self.heading_positions:
            heading_text = heading['text'].lower()

            # 计算标题匹配分数
            match_score = 0
            matched_keywords = []

            for keyword in keywords:
                keyword = keyword.lower()

                if use_fuzzy:
                    # 使用模糊匹配
                    try:
                        ratio = difflib.SequenceMatcher(None, keyword, heading_text).ratio() * 100
                        if ratio >= fuzzy_threshold:
                            match_score += 1 + (ratio / 100)  # 更高比率给更高分数
                            matched_keywords.append(keyword)
                        # 同时检查关键词是否是标题的子串
                        elif keyword in heading_text:
                            match_score += 1
                            matched_keywords.append(keyword)
                    except:
                        # 如果模糊匹配出错，回退到简单匹配
                        if keyword in heading_text:
                            match_score += 1
                            matched_keywords.append(keyword)
                else:
                    # 精确匹配
                    if keyword in heading_text:
                        match_score += 1
                        matched_keywords.append(keyword)

            if match_score > 0:
                matches.append({
                    'text': heading['text'],
                    'position': heading['position'],
                    'score': match_score,
                    'type': 'heading',
                    'keywords': matched_keywords
                })

        # 如果标题匹配不够，在内容中搜索
        if len(matches) < 10:
            # 搜索每个段落中的关键词
            paragraphs = re.split(r'\n\s*\n', self.knowledge_base)

            for para_idx, paragraph in enumerate(paragraphs):
                if not paragraph.strip():
                    continue

                # 查找段落在原始文本中的位置
                if para_idx == 0:
                    para_pos = 0
                else:
                    para_pos = self.knowledge_base.find(paragraph)

                # 计算段落的匹配分数
                para_score = 0
                para_matched_keywords = []

                for keyword in keywords:
                    keyword_lower = keyword.lower()
                    para_lower = paragraph.lower()

                    if use_fuzzy:
                        # 对于段落，先检查关键词是否包含（比完全模糊匹配更快）
                        # 但对较短的段落仍使用模糊匹配
                        if len(paragraph) < 500:
                            try:
                                ratio = difflib.SequenceMatcher(None, keyword_lower, para_lower).ratio() * 100
                                if ratio >= fuzzy_threshold:
                                    para_score += 0.5 + (ratio / 200)  # 权重低于直接匹配
                                    para_matched_keywords.append(keyword)
                            except:
                                # 如果模糊匹配出错，检查包含关系
                                if keyword_lower in para_lower:
                                    para_score += 1
                                    para_matched_keywords.append(keyword)
                        elif keyword_lower in para_lower:
                            para_score += 1
                            para_matched_keywords.append(keyword)
                    else:
                        # 精确匹配
                        if keyword_lower in para_lower:
                            para_score += 1
                            para_matched_keywords.append(keyword)

                if para_score > 0:
                    # 查找此段落的最近标题
                    nearest_heading = None
                    nearest_distance = float('inf')

                    for heading in self.heading_positions:
                        if heading['position'] <= para_pos:
                            distance = para_pos - heading['position']
                            if distance < nearest_distance:
                                nearest_distance = distance
                                nearest_heading = heading

                    heading_text = nearest_heading['text'] if nearest_heading else "无标题区域"

                    # 创建上下文摘要
                    if len(paragraph) > 100:
                        # 查找任何关键词的第一次出现
                        min_pos = len(paragraph)
                        for kw in para_matched_keywords:
                            kw_pos = paragraph.lower().find(kw.lower())
                            if kw_pos >= 0 and kw_pos < min_pos:
                                min_pos = kw_pos

                        # 创建以关键词为中心的摘要
                        start_pos = max(0, min_pos - 40)
                        end_pos = min(len(paragraph), min_pos + 60)
                        snippet = paragraph[start_pos:end_pos]
                        if start_pos > 0:
                            snippet = "..." + snippet
                        if end_pos < len(paragraph):
                            snippet = snippet + "..."
                    else:
                        snippet = paragraph

                    matches.append({
                        'text': f"{heading_text} - {snippet}",
                        'position': para_pos,
                        'score': para_score,
                        'type': 'content',
                        'keywords': para_matched_keywords
                    })

        # 按匹配分数排序
        matches.sort(key=lambda x: x['score'], reverse=True)

        # 限制显示的匹配数量
        max_matches = 30
        if len(matches) > max_matches:
            matches = matches[:max_matches]

        # 更新匹配列表
        for match in matches:
            display_text = match['text']
            if len(display_text) > 100:
                display_text = display_text[:97] + "..."

            # 添加关键词指示器
            keywords_str = ", ".join(match['keywords'][:3])
            if len(match['keywords']) > 3:
                keywords_str += "..."

            self.match_list.insert(tk.END, f"{display_text} [关键词: {keywords_str}]")

        # 高亮显示匹配项
        self.highlight_search_matches(query, matches)

        # 更新状态
        match_count = len(matches)
        self.status_bar.config(text=f"搜索完成: 找到 {match_count} 个匹配")

        # 保存匹配结果供后续使用
        self.current_matches = matches

        # 如果没有匹配项，显示提示
        if not matches:
            print(f"没有找到与'{query}'匹配的内容")
            # self.messagebox.showinfo("搜索结果", f"没有找到与'{query}'匹配的内容")
            self.status_bar.config(text=f"搜索结果：没有找到与'{query}'匹配的内容")

    def on_match_select(self, event):
        """处理匹配项选择事件"""
        selection = self.match_list.curselection()
        if not selection:
            return

        index = selection[0]
        if not hasattr(self, 'current_matches') or index >= len(self.current_matches):
            return

        # 获取选中的匹配项
        match = self.current_matches[index]
        position = match['position']
        match_text = match['text']
        match_keywords = match.get('keywords', [])

        # 判断是否为Markdown文件
        is_markdown = self.knowledge_path and self.knowledge_path.lower().endswith('.md')

        if is_markdown:
            # 多种匹配策略
            matched = False

            # 1. 如果是标题匹配，尝试查找确切的标题
            if match['type'] == 'heading':
                heading_text = match['text']

                # 先尝试在渲染后的文本中查找确切的标题
                start_pos = self.content_text.search(heading_text, "1.0", stopindex=tk.END, exact=True)
                if start_pos:
                    # 检查是否是真正的标题（不是正文中的相同文本）
                    tags_at_pos = self.content_text.tag_names(start_pos)
                    heading_tags = [tag for tag in tags_at_pos if tag.startswith('h')]

                    if heading_tags:  # 如果有h1, h2等标题标签
                        self.content_text.see(start_pos)

                        # 清除之前的高亮
                        self.content_text.config(state=tk.NORMAL)
                        self.content_text.tag_remove("position_highlight", "1.0", tk.END)

                        # 高亮该标题行及其下方几行
                        line_num = int(start_pos.split('.')[0])
                        for i in range(0, 5):  # 当前行和后4行
                            curr_line = line_num + i
                            if curr_line > 0:
                                line_start = f"{curr_line}.0"
                                try:
                                    line_end = f"{curr_line}.end"

                                    if i == 0:
                                        highlight_color = "yellow"  # 当前行亮黄色
                                    else:
                                        intensity = max(204, 255 - (i * 10))
                                        highlight_color = f"#FFFF{intensity:02X}"

                                    self.content_text.tag_add("position_highlight", line_start, line_end)
                                    self.content_text.tag_config("position_highlight", background=highlight_color)
                                except:
                                    pass

                        self.content_text.config(state=tk.DISABLED)

                        # 高亮目录中的相应项目
                        self.highlight_toc_for_position(position)
                        matched = True

            # 2. 如果是内容匹配，尝试使用关键词定位
            if not matched and match_keywords:
                # 按长度排序关键词，优先使用较长的关键词
                sorted_keywords = sorted(match_keywords, key=len, reverse=True)

                for keyword in sorted_keywords:
                    if len(keyword) < 3:  # 忽略太短的关键词
                        continue

                    # 查找关键词
                    pos = self.content_text.search(keyword, "1.0", stopindex=tk.END)
                    if pos:
                        self.content_text.see(pos)

                        # 清除之前的高亮
                        self.content_text.config(state=tk.NORMAL)
                        self.content_text.tag_remove("position_highlight", "1.0", tk.END)

                        # 高亮当前行和周围几行
                        line_num = int(pos.split('.')[0])
                        for i in range(-1, 5):  # 前1行和后4行
                            curr_line = line_num + i
                            if curr_line > 0:
                                line_start = f"{curr_line}.0"
                                try:
                                    line_end = f"{curr_line}.end"

                                    if i == 0:
                                        highlight_color = "yellow"  # 当前行亮黄色
                                    elif i > 0:
                                        intensity = max(204, 255 - (i * 10))
                                        highlight_color = f"#FFFF{intensity:02X}"
                                    else:
                                        highlight_color = "#FFFFDD"  # 前一行浅黄色

                                    self.content_text.tag_add("position_highlight", line_start, line_end)
                                    self.content_text.tag_config("position_highlight", background=highlight_color)
                                except:
                                    pass

                        self.content_text.config(state=tk.DISABLED)
                        matched = True
                        break

            # 3. 尝试使用匹配文本的前半部分（通常是标题部分）
            if not matched and ' - ' in match_text:
                title_part = match_text.split(' - ')[0].strip()
                if len(title_part) > 3:  # 确保足够长以减少误匹配
                    pos = self.content_text.search(title_part, "1.0", stopindex=tk.END)
                    if pos:
                        self.content_text.see(pos)

                        # 清除之前的高亮
                        self.content_text.config(state=tk.NORMAL)
                        self.content_text.tag_remove("position_highlight", "1.0", tk.END)

                        # 高亮当前行和周围几行
                        line_num = int(pos.split('.')[0])
                        for i in range(-1, 5):
                            curr_line = line_num + i
                            if curr_line > 0:
                                line_start = f"{curr_line}.0"
                                try:
                                    line_end = f"{curr_line}.end"

                                    if i == 0:
                                        highlight_color = "yellow"
                                    elif i > 0:
                                        intensity = max(204, 255 - (i * 10))
                                        highlight_color = f"#FFFF{intensity:02X}"
                                    else:
                                        highlight_color = "#FFFFDD"

                                    self.content_text.tag_add("position_highlight", line_start, line_end)
                                    self.content_text.tag_config("position_highlight", background=highlight_color)
                                except:
                                    pass

                        self.content_text.config(state=tk.DISABLED)
                        matched = True

            # 4. 如果以上策略都失败，尝试提取上下文并搜索
            if not matched:
                # 提取原始位置附近的上下文
                context_start = max(0, position - 30)
                context_end = min(len(self.knowledge_base), position + 30)
                context = self.knowledge_base[context_start:context_end]

                # 尝试找到上下文中的一些独特词语
                words = re.findall(r'\b\w{4,}\b', context)
                words.sort(key=len, reverse=True)

                search_terms = []
                for word in words:
                    if word not in search_terms and len(word) > 4:
                        search_terms.append(word)
                        if len(search_terms) >= 5:
                            break

                # 尝试使用这些词定位
                for term in search_terms:
                    pos = self.content_text.search(term, "1.0", stopindex=tk.END)
                    if pos:
                        self.content_text.see(pos)

                        # 清除之前的高亮
                        self.content_text.config(state=tk.NORMAL)
                        self.content_text.tag_remove("position_highlight", "1.0", tk.END)

                        # 高亮当前行和周围几行
                        line_num = int(pos.split('.')[0])
                        for i in range(-1, 5):
                            curr_line = line_num + i
                            if curr_line > 0:
                                line_start = f"{curr_line}.0"
                                try:
                                    line_end = f"{curr_line}.end"

                                    if i == 0:
                                        highlight_color = "yellow"
                                    elif i > 0:
                                        intensity = max(204, 255 - (i * 10))
                                        highlight_color = f"#FFFF{intensity:02X}"
                                    else:
                                        highlight_color = "#FFFFDD"

                                    self.content_text.tag_add("position_highlight", line_start, line_end)
                                    self.content_text.tag_config("position_highlight", background=highlight_color)
                                except:
                                    pass

                        self.content_text.config(state=tk.DISABLED)
                        matched = True
                        break

            # 如果所有尝试都失败，回退到默认方法
            if not matched:
                self.scroll_to_position(position)

                # 如果这是一个标题，同时高亮目录中的相应项目
                if match['type'] == 'heading':
                    self.highlight_toc_for_position(position)
        else:
            # 非Markdown文件使用原始方法
            self.scroll_to_position(position)

            # 如果这是一个标题，同时高亮目录中的相应项目
            if match['type'] == 'heading':
                self.highlight_toc_for_position(position)
    def on_toc_select(self, event):

        """处理目录项选择事件"""
        selected_items = self.toc_tree.selection()
        if not selected_items:
            return

        item_id = selected_items[0]

        # 获取存储在树项目中的位置值
        values = self.toc_tree.item(item_id, 'values')
        if not values:
            return

        position = values[0]

        # 滚动到该位置
        self.scroll_to_position(int(position))

    def highlight_toc_for_position(self, position):
        """高亮对应位置的目录项"""

        # 查找该位置的目录项，使用递归方法而不是一次性获取所有子节点
        def search_toc_items(parent=''):
            for item_id in self.toc_tree.get_children(parent):
                values = self.toc_tree.item(item_id, 'values')
                if values and int(values[0]) == position:
                    # 选中此项
                    self.toc_tree.selection_set(item_id)
                    self.toc_tree.see(item_id)
                    return True

                # 递归搜索子项
                if search_toc_items(item_id):
                    return True
            return False

        search_toc_items()

    def scroll_to_position(self, position):
        """滚动内容到指定位置，支持Markdown渲染"""
        is_markdown = self.knowledge_path and self.knowledge_path.lower().endswith('.md')

        if is_markdown:
            # 检查是否有位置映射
            if hasattr(self, 'position_mapping') and position in self.position_mapping:
                # 直接使用映射的位置
                mark_position = self.position_mapping[position]
                self.content_text.config(state=tk.NORMAL)
                self.content_text.mark_set(tk.INSERT, mark_position)
                self.content_text.see(mark_position)

                # 计算行号以进行高亮
                line_num = int(mark_position.split('.')[0])

                # 清除之前的高亮
                self.content_text.tag_remove("position_highlight", "1.0", tk.END)

                # 高亮显示当前行和周围几行
                for i in range(-1, 5):  # 前1行和后4行
                    curr_line = line_num + i
                    if curr_line > 0:
                        line_start = f"{curr_line}.0"
                        try:
                            line_end = f"{curr_line}.end"

                            if i == 0:
                                highlight_color = "yellow"  # 当前行亮黄色
                            elif i > 0:
                                intensity = max(204, 255 - (i * 10))
                                highlight_color = f"#FFFF{intensity:02X}"
                            else:
                                highlight_color = "#FFFFDD"  # 前一行浅黄色

                            self.content_text.tag_add("position_highlight", line_start, line_end)
                            self.content_text.tag_config("position_highlight", background=highlight_color)
                        except:
                            pass

                self.content_text.config(state=tk.DISABLED)
                return

            # 查找最接近该位置的标题
            nearest_heading = None
            nearest_distance = float('inf')

            for heading in self.heading_positions:
                if heading['position'] <= position:
                    distance = position - heading['position']
                    if distance < nearest_distance:
                        nearest_distance = distance
                        nearest_heading = heading

            if nearest_heading and hasattr(nearest_heading, 'rendered_position') and nearest_heading[
                'rendered_position']:
                # 使用渲染后的位置
                mark_position = nearest_heading['rendered_position']
                self.content_text.config(state=tk.NORMAL)
                self.content_text.mark_set(tk.INSERT, mark_position)
                self.content_text.see(mark_position)

                # 计算行号以进行高亮
                line_num = int(mark_position.split('.')[0])

                # 清除之前的高亮
                self.content_text.tag_remove("position_highlight", "1.0", tk.END)

                # 高亮显示当前行和周围几行
                for i in range(-1, 5):  # 前1行和后4行
                    curr_line = line_num + i
                    if curr_line > 0:
                        line_start = f"{curr_line}.0"
                        try:
                            line_end = f"{curr_line}.end"

                            if i == 0:
                                highlight_color = "yellow"  # 当前行亮黄色
                            elif i > 0:
                                intensity = max(204, 255 - (i * 10))
                                highlight_color = f"#FFFF{intensity:02X}"
                            else:
                                highlight_color = "#FFFFDD"  # 前一行浅黄色

                            self.content_text.tag_add("position_highlight", line_start, line_end)
                            self.content_text.tag_config("position_highlight", background=highlight_color)
                        except:
                            pass

                self.content_text.config(state=tk.DISABLED)
                return

            # 如果找不到精确映射，尝试上下文匹配
            # 提取原始位置附近的上下文
            context_start = max(0, position - 30)
            context_end = min(len(self.knowledge_base), position + 30)
            context = self.knowledge_base[context_start:context_end]

            # 尝试找到上下文中的一些独特词语进行搜索
            words = re.findall(r'\b\w{4,}\b', context)  # 提取4个字符以上的词
            search_terms = []

            # 按长度排序，优先使用较长的词
            words.sort(key=len, reverse=True)

            # 选取前5个不同的词
            for word in words:
                if word not in search_terms and len(word) > 4:
                    search_terms.append(word)
                    if len(search_terms) >= 5:
                        break

            # 尝试使用这些词定位
            for term in search_terms:
                pos = self.content_text.search(term, "1.0", stopindex=tk.END)
                if pos:
                    self.content_text.config(state=tk.NORMAL)
                    self.content_text.mark_set(tk.INSERT, pos)
                    self.content_text.see(pos)

                    # 计算行号以进行高亮
                    line_num = int(pos.split('.')[0])

                    # 清除之前的高亮
                    self.content_text.tag_remove("position_highlight", "1.0", tk.END)

                    # 高亮显示当前行和周围几行
                    for i in range(-1, 5):  # 前1行和后4行
                        curr_line = line_num + i
                        if curr_line > 0:
                            line_start = f"{curr_line}.0"
                            try:
                                line_end = f"{curr_line}.end"

                                if i == 0:
                                    highlight_color = "yellow"  # 当前行亮黄色
                                elif i > 0:
                                    intensity = max(204, 255 - (i * 10))
                                    highlight_color = f"#FFFF{intensity:02X}"
                                else:
                                    highlight_color = "#FFFFDD"  # 前一行浅黄色

                                self.content_text.tag_add("position_highlight", line_start, line_end)
                                self.content_text.tag_config("position_highlight", background=highlight_color)
                            except:
                                pass

                    self.content_text.config(state=tk.DISABLED)
                    return

        # 默认处理方法（非Markdown或搜索失败）
        line_number = self.knowledge_base.count('\n', 0, position) + 1

        # 设置标记以滚动到该位置
        mark_position = f"{line_number}.0"
        self.content_text.config(state=tk.NORMAL)
        self.content_text.mark_set(tk.INSERT, mark_position)
        self.content_text.see(mark_position)

        # 清除之前的高亮
        self.content_text.tag_remove("position_highlight", "1.0", tk.END)

        # 高亮显示当前行和周围几行
        for i in range(-1, 5):  # 前1行和后4行
            curr_line = line_number + i
            if curr_line > 0:
                line_start = f"{curr_line}.0"
                try:
                    line_end = f"{curr_line}.end"

                    if i == 0:
                        highlight_color = "yellow"  # 当前行亮黄色
                    elif i > 0:
                        intensity = max(204, 255 - (i * 10))
                        highlight_color = f"#FFFF{intensity:02X}"
                    else:
                        highlight_color = "#FFFFDD"  # 前一行浅黄色

                    self.content_text.tag_add("position_highlight", line_start, line_end)
                    self.content_text.tag_config("position_highlight", background=highlight_color)
                except:
                    pass

        self.content_text.config(state=tk.DISABLED)

    def find_content_by_context(self, original_position, context_length=50):
        """通过上下文找到渲染后的文本位置"""
        # 获取原始文档中的上下文
        start = max(0, original_position - context_length)
        end = min(len(self.knowledge_base), original_position + context_length)
        context = self.knowledge_base[start:end]

        # 清理上下文中的Markdown标记
        clean_context = re.sub(r'[#*`_]', '', context)
        words = clean_context.split()

        # 提取一些独特的词语作为搜索锚点
        search_anchors = []
        for word in words:
            if len(word) > 4 and word.isalnum():  # 选择较长的单词作为锚点
                search_anchors.append(word)

        # 限制锚点数量
        search_anchors = search_anchors[:5]

        # 在渲染后的文本中寻找这些锚点
        for anchor in search_anchors:
            pos = self.content_text.search(anchor, "1.0", stopindex=tk.END)
            if pos:
                # 找到了一个锚点
                return pos

        return None

    def show_help(self):
        """显示使用帮助"""
        help_text = """
            知识库语音导航系统 - 使用帮助
            
            基本操作:
            -----------
            1. 加载知识库:
               - 点击"文件" → "打开知识库"选择Markdown或文本文件
            
            2. 浏览内容:
               - 直接滚动浏览文档内容
               - 点击右侧目录树跳转到对应章节
            
            3. 搜索功能:
               - 在搜索框输入关键词，按Enter或点击"搜索"
               - 点击左侧结果列表跳转到匹配位置
               - 使用"清除"按钮重置搜索结果
            
            4. 语音功能:
               - 点击"开始监听"启动语音识别
               - 说出要查找的内容或关键词
               - 使用"处理长对话"分析多句组合查询
            
            高级功能:
            -----------
            - 更改语音引擎: "设置" → "语音识别引擎"
            - 调整模糊匹配: "设置" → "搜索设置"和"模糊匹配灵敏度"
            - 字体调整: "视图" → "放大字体"/"缩小字体"
            - 目录展开/折叠: "视图" → "展开所有目录"/"折叠所有目录"
            
            快捷操作:
            -----------
            - 搜索框中按Enter直接搜索
            - 语音识别后自动执行搜索
            - 点击搜索结果或目录项快速跳转
        """

        help_window = tk.Toplevel(self.root)
        help_window.title("使用帮助")
        help_window.geometry("600x500")
        help_window.transient(self.root)

        help_text_widget = scrolledtext.ScrolledText(help_window, wrap=tk.WORD, width=80, height=30)
        help_text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        help_text_widget.insert(tk.END, help_text)
        help_text_widget.config(state=tk.DISABLED)

        close_button = tk.Button(help_window, text="关闭", command=help_window.destroy, width=10, height=1)
        close_button.pack(pady=10)

    def show_about(self):
        """显示关于信息"""
        about_text = """
            知识库语音导航系统
            
            版本: 1.0
            
            这是一个帮助用户通过语音和文本搜索快速浏览知识库的工具。
            支持Markdown和文本格式的知识库文件，提供语音控制、模糊匹配等功能。
            
            功能特点:
            - 支持语音搜索和导航
            - 智能关键词提取和模糊匹配
            - 多种语音引擎支持
            - 长语句理解和处理
            
            © 2025 知识库语音导航系统团队
        """
        self.messagebox.showinfo("关于", about_text)

def main():
    try:
        # 禁用系统提示音
        disable_system_sounds()

        # 创建主窗口
        root = tk.Tk()
        app = KnowledgeNavigator(root)

        # 使窗口处于屏幕中央
        root.update_idletasks()
        width = root.winfo_width()
        height = root.winfo_height()
        x = (root.winfo_screenwidth() // 2) - (width // 2)
        y = (root.winfo_screenheight() // 2) - (height // 2)
        root.geometry(f"{width}x{height}+{x}+{y}")

        root.mainloop()
    except Exception as e:
        print(f"程序运行出错: {str(e)}")
        messagebox.showinfo("错误", f"程序运行出错: {str(e)}")
        # self.status_bar.config(text=f"提示：没有识别到完整的语音内容")


if __name__ == "__main__":
    main()