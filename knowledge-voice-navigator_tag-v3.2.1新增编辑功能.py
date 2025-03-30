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
        self.root.bind("<Configure>", self.on_window_resize)

    def on_window_resize(self, event):
        # 只有当窗口宽度变化时才重新布局标签
        # 避免窗口高度变化也触发重绘
        if hasattr(self, 'last_width') and self.last_width != self.root.winfo_width():
            self.create_tag_frame()
        self.last_width = self.root.winfo_width()

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
        # 在文件菜单中添加编辑功能
        self.file_menu.add_command(label="编辑文档", command=self.enable_edit_mode, state=tk.DISABLED)

        self.file_menu.add_separator()  # 在"退出"前添加分隔线
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
        """创建标签框架 - 多行显示版本"""
        # 删除现有标签框架
        if hasattr(self, 'tag_frame_main') and self.tag_frame_main:
            try:
                self.tag_frame_main.destroy()
            except tk.TclError:
                pass

        # 创建主框架
        tag_main_frame = tk.Frame(self.root)
        tag_main_frame.pack(fill=tk.X, padx=10, pady=(0, 5))

        # 创建标题和添加按钮的行
        header_frame = tk.Frame(tag_main_frame)
        header_frame.pack(fill=tk.X, pady=(3, 0))

        # 添加标签标题
        tag_label = tk.Label(header_frame, text="常用搜索:", font=("Arial", 9, "bold"))
        tag_label.pack(side=tk.LEFT, padx=(0, 5))

        # 添加标签按钮放在右侧
        add_tag_button = tk.Button(
            header_frame,
            text="+ 添加标签",
            padx=5,
            relief=tk.GROOVE,
            bg="#e0e0e0",
            activebackground="#d0d0d0",
            cursor="hand2",
            command=self.add_tag_dialog
        )
        add_tag_button.pack(side=tk.RIGHT, padx=5)

        # 创建标签容器（替换原来的单行框架）
        self.tag_frame = tk.Frame(tag_main_frame)
        self.tag_frame.pack(fill=tk.X, pady=5)

        # 清除旧的标签按钮列表
        self.tag_buttons = []

        # 固定每行显示的标签数
        tags_per_row = 10  # 可以调整这个值来改变每行标签数量

        # 配置每行最大宽度和标签处理
        max_width = self.root.winfo_width() - 10  # 留出边距
        # tags_per_row = max(3, min(8, max_width // 120))  # 根据窗口宽度计算每行标签数

        # 为标签创建多行
        if hasattr(self, 'tags') and self.tags:
            current_row = tk.Frame(self.tag_frame)
            current_row.pack(fill=tk.X, pady=2)

            row_count = 0
            current_width = 0

            for index, tag in enumerate(self.tags):
                # 预估标签宽度 (每个字符约8像素，再加上额外的padding和按钮)
                tag_width = len(tag) * 8 + 50

                # 如果这个标签会导致当前行超过最大宽度或达到每行最大标签数，创建新行
                if row_count >= tags_per_row or current_width + tag_width > max_width:
                    current_row = tk.Frame(self.tag_frame)
                    current_row.pack(fill=tk.X, pady=2)
                    row_count = 0
                    current_width = 0

                # 在当前行创建标签
                tag_button_info = self.create_tag_button(tag, parent=current_row)
                # 更新当前行计数和宽度估计
                row_count += 1
                current_width += tag_width

        self.tag_frame_main = tag_main_frame

    def create_tag_button(self, tag_text, parent=None):
        """创建标签按钮，支持指定父容器"""
        # 如果没有指定父容器，默认使用self.tag_frame
        if parent is None:
            parent = self.tag_frame

        # 生成一个基于标签文本的柔和背景色
        color_seed = hash(tag_text) % 1000
        r = min(230, max(180, (color_seed % 5) * 10 + 180))
        g = min(240, max(200, ((color_seed // 5) % 5) * 10 + 200))
        b = min(250, max(220, ((color_seed // 25) % 5) * 10 + 220))
        bg_color = f"#{r:02x}{g:02x}{b:02x}"

        # 创建标签容器
        tag_container = tk.Frame(parent, bd=1, relief=tk.RAISED, bg=bg_color)
        tag_container.pack(side=tk.LEFT, padx=3, pady=3)

        # 创建标签按钮
        tag_button = tk.Button(
            tag_container,
            text=tag_text,
            font=("Arial", 9),
            padx=5,
            pady=2,
            relief=tk.FLAT,
            bg=bg_color,
            activebackground="#d0d0d0",
            cursor="hand2",
            command=lambda t=tag_text: self.search_tag(t)
        )
        tag_button.pack(side=tk.LEFT)

        # 添加标签计数显示
        count_label = tk.Label(
            tag_container,
            text="0",  # 初始计数为0，将在搜索时更新
            font=("Arial", 8),
            bg=bg_color,
            fg="#555555",
            width=2,
            padx=1
        )
        count_label.pack(side=tk.LEFT, padx=(0, 2))

        # 创建小型关闭按钮
        close_button = tk.Button(
            tag_container,
            text="×",
            font=("Arial", 8, "bold"),
            width=1,
            height=1,
            padx=0,
            pady=0,
            relief=tk.FLAT,
            bg=bg_color,
            activebackground="#ff9999",
            cursor="hand2",
            command=lambda t=tag_text: self.delete_tag(t)
        )
        close_button.pack(side=tk.RIGHT)

        # 绑定悬停效果
        def on_tag_enter(e):
            tag_container.config(relief=tk.RAISED)
            tag_button.config(bg="#d0d0d0")
            count_label.config(bg="#d0d0d0")
            close_button.config(bg="#d0d0d0")

        def on_tag_leave(e):
            tag_container.config(relief=tk.RAISED)
            tag_button.config(bg=bg_color)
            count_label.config(bg=bg_color)
            close_button.config(bg=bg_color)

        tag_container.bind("<Enter>", on_tag_enter)
        tag_container.bind("<Leave>", on_tag_leave)
        tag_button.bind("<Enter>", on_tag_enter)
        tag_button.bind("<Leave>", on_tag_leave)

        # 绑定关闭按钮的悬停效果
        close_button.bind("<Enter>", lambda e: close_button.config(bg="#ff9999", fg="white"))
        close_button.bind("<Leave>", lambda e: close_button.config(bg=bg_color if not tag_container.winfo_containing(
            e.x_root, e.y_root) == tag_container else "#d0d0d0", fg="black"))

        # 添加右键菜单
        tag_menu = tk.Menu(tag_button, tearoff=0)
        tag_menu.add_command(label="编辑标签", command=lambda t=tag_text: self.edit_tag(t))
        tag_menu.add_command(label="删除标签", command=lambda t=tag_text: self.delete_tag(t))
        tag_menu.add_separator()
        tag_menu.add_command(label="复制到剪贴板", command=lambda t=tag_text: self.copy_to_clipboard(t))

        # 绑定右键菜单
        tag_button.bind("<Button-3>", lambda event, menu=tag_menu: menu.post(event.x_root, event.y_root))

        # 保存成元组格式，包含计数标签
        tag_info = (tag_container, tag_button, close_button, count_label, tag_text)
        self.tag_buttons.append(tag_info)

        return tag_info




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
        """显示添加新标签的对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title("添加新标签")
        dialog.transient(self.root)
        dialog.grab_set()

        # 计算位置
        dialog.geometry(f"300x120+{self.root.winfo_rootx() + 50}+{self.root.winfo_rooty() + 50}")

        # 添加标签和输入框
        tk.Label(dialog, text="输入标签内容:").pack(pady=(10, 5))
        tag_var = tk.StringVar()
        entry = tk.Entry(dialog, textvariable=tag_var, width=30)
        entry.pack(pady=5, padx=10)
        entry.focus_set()

        # 按钮框架
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

        # 绑定回车键
        entry.bind('<Return>', lambda e: save_tag())

        # 等待对话框关闭
        self.root.wait_window(dialog)

    def manage_tags_dialog(self):
        """标签管理对话框 - 新增功能"""
        dialog = tk.Toplevel(self.root)
        dialog.title("标签管理")
        dialog.transient(self.root)
        dialog.grab_set()

        # 计算屏幕中央位置
        window_width = 400
        window_height = 450
        screen_width = dialog.winfo_screenwidth()
        screen_height = dialog.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        dialog.geometry(f"{window_width}x{window_height}+{x}+{y}")

        # 创建说明标签
        header_frame = tk.Frame(dialog, padx=10, pady=10, bg="#f0f0f0")
        header_frame.pack(fill=tk.X)

        tk.Label(
            header_frame,
            text="管理常用搜索标签",
            font=("Arial", 12, "bold"),
            bg="#f0f0f0"
        ).pack(anchor=tk.W)

        tk.Label(
            header_frame,
            text="您可以添加、编辑、删除或重新排序标签。\n标签数量上限为10个。",
            justify=tk.LEFT,
            bg="#f0f0f0"
        ).pack(anchor=tk.W, pady=(5, 0))

        # 创建标签列表框架
        list_frame = tk.Frame(dialog, padx=10, pady=10)
        list_frame.pack(fill=tk.BOTH, expand=True)

        # 创建带滚动条的列表框
        tk.Label(list_frame, text="当前标签:").pack(anchor=tk.W)

        # 创建列表框和滚动条
        tag_listbox_frame = tk.Frame(list_frame)
        tag_listbox_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

        tag_listbox = tk.Listbox(
            tag_listbox_frame,
            selectmode=tk.SINGLE,
            activestyle="dotbox",
            font=("Arial", 10),
            height=10
        )
        tag_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(tag_listbox_frame, command=tag_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tag_listbox.config(yscrollcommand=scrollbar.set)

        # 填充标签列表
        for tag in self.tags:
            tag_listbox.insert(tk.END, tag)

        # 创建按钮框架
        button_frame = tk.Frame(list_frame)
        button_frame.pack(fill=tk.X, pady=10)

        # 添加按钮
        add_button = tk.Button(
            button_frame,
            text="添加",
            width=8,
            command=lambda: add_tag_dialog()
        )
        add_button.pack(side=tk.LEFT, padx=5)

        edit_button = tk.Button(
            button_frame,
            text="编辑",
            width=8,
            command=lambda: edit_selected_tag()
        )
        edit_button.pack(side=tk.LEFT, padx=5)

        delete_button = tk.Button(
            button_frame,
            text="删除",
            width=8,
            command=lambda: delete_selected_tag()
        )
        delete_button.pack(side=tk.LEFT, padx=5)

        # 排序按钮
        move_up_button = tk.Button(
            button_frame,
            text="上移",
            width=8,
            command=lambda: move_tag(-1)
        )
        move_up_button.pack(side=tk.LEFT, padx=5)

        move_down_button = tk.Button(
            button_frame,
            text="下移",
            width=8,
            command=lambda: move_tag(1)
        )
        move_down_button.pack(side=tk.LEFT, padx=5)

        # 底部按钮框架
        bottom_frame = tk.Frame(dialog, padx=10, pady=10)
        bottom_frame.pack(fill=tk.X)

        # 添加导入导出按钮
        import_export_frame = tk.Frame(bottom_frame)
        import_export_frame.pack(fill=tk.X, pady=(0, 10))

        import_button = tk.Button(
            import_export_frame,
            text="导入标签",
            width=10,
            command=lambda: import_tags()
        )
        import_button.pack(side=tk.LEFT, padx=5)

        export_button = tk.Button(
            import_export_frame,
            text="导出标签",
            width=10,
            command=lambda: export_tags()
        )
        export_button.pack(side=tk.LEFT, padx=5)

        # 关闭按钮
        close_button = tk.Button(
            bottom_frame,
            text="关闭",
            width=10,
            command=dialog.destroy
        )
        close_button.pack(side=tk.RIGHT, padx=5)

        # 内部函数
        def add_tag_dialog():
            """添加新标签对话框"""
            if len(self.tags) >= 10:
                self.messagebox.showinfo("提示", "标签数量已达上限(10个)")
                return

            # 创建子对话框
            add_dialog = tk.Toplevel(dialog)
            add_dialog.title("添加新标签")
            add_dialog.transient(dialog)
            add_dialog.grab_set()

            # 居中显示
            add_dialog.geometry(f"300x150+{x + 50}+{y + 100}")

            # 添加标签和输入框
            tk.Label(add_dialog, text="输入新标签:", padx=10, pady=10).pack()

            tag_var = tk.StringVar()
            entry = tk.Entry(add_dialog, textvariable=tag_var, width=30)
            entry.pack(padx=10, pady=5)
            entry.focus_set()

            # 按钮框架
            btn_frame = tk.Frame(add_dialog)
            btn_frame.pack(pady=15)

            # 保存函数
            def save_new_tag():
                new_tag = tag_var.get().strip()
                if not new_tag:
                    self.messagebox.showinfo("错误", "标签不能为空")
                    return

                if new_tag in self.tags:
                    self.messagebox.showinfo("错误", "标签已存在")
                    return

                # 添加新标签
                self.tags.append(new_tag)
                tag_listbox.insert(tk.END, new_tag)
                self.save_tags()

                # 关闭对话框
                add_dialog.destroy()

            # 添加按钮
            save_btn = tk.Button(btn_frame, text="保存", width=10, command=save_new_tag)
            save_btn.pack(side=tk.LEFT, padx=5)

            cancel_btn = tk.Button(btn_frame, text="取消", width=10, command=add_dialog.destroy)
            cancel_btn.pack(side=tk.LEFT, padx=5)

            # 绑定回车键
            entry.bind("<Return>", lambda e: save_new_tag())

        def edit_selected_tag():
            """编辑选中的标签"""
            selection = tag_listbox.curselection()
            if not selection:
                self.messagebox.showinfo("提示", "请先选择一个标签")
                return

            index = selection[0]
            old_tag = self.tags[index]

            # 创建子对话框
            edit_dialog = tk.Toplevel(dialog)
            edit_dialog.title("编辑标签")
            edit_dialog.transient(dialog)
            edit_dialog.grab_set()

            # 居中显示
            edit_dialog.geometry(f"300x150+{x + 50}+{y + 100}")

            # 添加标签和输入框
            tk.Label(edit_dialog, text="编辑标签:", padx=10, pady=10).pack()

            tag_var = tk.StringVar(value=old_tag)
            entry = tk.Entry(edit_dialog, textvariable=tag_var, width=30)
            entry.pack(padx=10, pady=5)
            entry.focus_set()

            # 按钮框架
            btn_frame = tk.Frame(edit_dialog)
            btn_frame.pack(pady=15)

            # 保存函数
            def save_edited_tag():
                new_tag = tag_var.get().strip()
                if not new_tag:
                    self.messagebox.showinfo("错误", "标签不能为空")
                    return

                if new_tag in self.tags and new_tag != old_tag:
                    self.messagebox.showinfo("错误", "标签已存在")
                    return

                # 更新标签
                self.tags[index] = new_tag
                tag_listbox.delete(index)
                tag_listbox.insert(index, new_tag)
                self.save_tags()

                # 关闭对话框
                edit_dialog.destroy()

            # 添加按钮
            save_btn = tk.Button(btn_frame, text="保存", width=10, command=save_edited_tag)
            save_btn.pack(side=tk.LEFT, padx=5)

            cancel_btn = tk.Button(btn_frame, text="取消", width=10, command=edit_dialog.destroy)
            cancel_btn.pack(side=tk.LEFT, padx=5)

            # 绑定回车键
            entry.bind("<Return>", lambda e: save_edited_tag())

        def delete_selected_tag():
            """删除选中的标签"""
            selection = tag_listbox.curselection()
            if not selection:
                self.messagebox.showinfo("提示", "请先选择一个标签")
                return

            index = selection[0]
            tag = self.tags[index]

            # 确认删除
            if not self.messagebox.showinfo("确认", f"确定要删除标签 '{tag}' 吗?"):
                return

            # 删除标签
            self.tags.pop(index)
            tag_listbox.delete(index)
            self.save_tags()

        def move_tag(direction):
            """移动标签位置"""
            selection = tag_listbox.curselection()
            if not selection:
                self.messagebox.showinfo("提示", "请先选择一个标签")
                return

            index = selection[0]
            new_index = index + direction

            # 检查边界
            if new_index < 0 or new_index >= len(self.tags):
                return

            # 交换位置
            self.tags[index], self.tags[new_index] = self.tags[new_index], self.tags[index]

            # 更新列表显示
            tag_text = tag_listbox.get(index)
            tag_listbox.delete(index)
            tag_listbox.insert(new_index, tag_text)
            tag_listbox.selection_set(new_index)

            # 保存标签顺序
            self.save_tags()

        def import_tags():
            """从文件导入标签"""
            file_path = filedialog.askopenfilename(
                title="选择标签文件",
                filetypes=[("标签文件", "*.tags"), ("文本文件", "*.txt"), ("所有文件", "*.*")]
            )

            if not file_path:
                return

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    imported_tags = [line.strip() for line in f if line.strip()]

                # 合并标签，确保没有重复
                new_tags = []
                for tag in imported_tags:
                    if tag not in self.tags and tag not in new_tags:
                        new_tags.append(tag)

                # 检查标签总数量
                if len(self.tags) + len(new_tags) > 10:
                    overflow = len(self.tags) + len(new_tags) - 10
                    self.messagebox.showinfo("提示",
                                             f"导入的标签过多，总数超过10个。\n"
                                             f"将只导入前{len(new_tags) - overflow}个新标签。")
                    new_tags = new_tags[:len(new_tags) - overflow]

                # 添加新标签
                for tag in new_tags:
                    self.tags.append(tag)
                    tag_listbox.insert(tk.END, tag)

                # 保存并更新
                self.save_tags()
                self.messagebox.showinfo("成功", f"已导入{len(new_tags)}个新标签")

            except Exception as e:
                self.messagebox.showerror("错误", f"导入标签失败: {str(e)}")

        def export_tags():
            """导出标签到文件"""
            if not self.tags:
                self.messagebox.showinfo("提示", "没有标签可导出")
                return

            file_path = filedialog.asksaveasfilename(
                title="导出标签",
                defaultextension=".tags",
                filetypes=[("标签文件", "*.tags"), ("文本文件", "*.txt"), ("所有文件", "*.*")]
            )

            if not file_path:
                return

            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    for tag in self.tags:
                        f.write(f"{tag}\n")

                self.messagebox.showinfo("成功", f"已成功导出{len(self.tags)}个标签到文件")

            except Exception as e:
                self.messagebox.showerror("错误", f"导出标签失败: {str(e)}")

        # 帮助函数 - 更新按钮状态
        def update_button_states(event=None):
            selection = tag_listbox.curselection()
            if selection:
                index = selection[0]
                # 启用编辑和删除按钮
                edit_button.config(state=tk.NORMAL)
                delete_button.config(state=tk.NORMAL)

                # 设置移动按钮状态
                move_up_button.config(state=tk.NORMAL if index > 0 else tk.DISABLED)
                move_down_button.config(state=tk.NORMAL if index < len(self.tags) - 1 else tk.DISABLED)
            else:
                # 禁用所有需要选择的按钮
                edit_button.config(state=tk.DISABLED)
                delete_button.config(state=tk.DISABLED)
                move_up_button.config(state=tk.DISABLED)
                move_down_button.config(state=tk.DISABLED)

        # 初始化按钮状态
        update_button_states()

        # 绑定选择事件
        tag_listbox.bind("<<ListboxSelect>>", update_button_states)

        # 键盘快捷键
        dialog.bind("<Delete>", lambda e: delete_selected_tag())
        dialog.bind("<F2>", lambda e: edit_selected_tag())

    def copy_to_clipboard(self, text):
        """复制文本到剪贴板"""
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.status_bar.config(text=f"已复制 '{text}' 到剪贴板")

    def update_tag_counts(self):
        """更新标签上显示的匹配计数 - 修复版本"""
        # 如果没有加载知识库，不需要更新
        if not self.knowledge_base:
            return

        # 为每个标签执行搜索（不显示结果）并更新计数
        for tag_info in self.tag_buttons:
            # 从元组中提取各个组件 - 兼容修复后的结构
            tag_container, tag_button, close_button, count_label, tag_text = tag_info

            # 提取关键词
            keywords = self.extract_keywords(tag_text)

            # 计算匹配数
            match_count = 0

            # 在标题中搜索
            for heading in self.heading_positions:
                heading_text = heading['text'].lower()

                for keyword in keywords:
                    if keyword.lower() in heading_text:
                        match_count += 1
                        break  # 每个标题只计数一次

            # 如果匹配数超过0，更新计数标签
            count_label.config(text=str(match_count) if match_count <= 99 else "99+")

            # 颜色反映匹配数量
            if match_count == 0:
                count_label.config(fg="#999999")
            elif match_count < 5:
                count_label.config(fg="#555555")
            else:
                count_label.config(fg="#0066CC", font=("Arial", 8, "bold"))
                
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
        """删除标签"""
        if tag in self.tags:
            # 使用messagebox替代self.messagebox.showinfo，因为后者可能返回类型不正确
            result = messagebox.askyesno("确认", f"确定要删除标签 '{tag}' 吗?", parent=self.root)
            if result:  # 确认删除
                self.tags.remove(tag)
                self.create_tag_frame()  # 重建标签框架
                self.save_tags()  # 保存标签状态
                self.status_bar.config(text=f"已删除标签: {tag}")

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
                self.update_tag_counts()

                # 在成功加载知识库后添加:
                self.file_menu.entryconfig("编辑文档", state=tk.NORMAL)

            except Exception as e:
                print(f"加载知识库失败: {str(e)}")
                # self.messagebox.showerror("错误", f"加载知识库失败: {str(e)}")
                self.status_bar.config(text=f"错误: {str(e)}")

    # 以下是需要添加到KnowledgeNavigator类中的方法

    def enable_edit_mode(self):
        """启用文档编辑模式"""
        if not self.knowledge_base:
            self.messagebox.showinfo("提示", "请先加载知识库文件")
            return

        # 将文本区域设为可编辑状态
        self.content_text.config(state=tk.NORMAL)

        # 记录原始内容，以便取消编辑
        if not hasattr(self, 'original_content'):
            self.original_content = self.knowledge_base

        # 更新状态栏
        self.status_bar.config(text="编辑模式: 已启用")

        # 禁用其他可能干扰编辑的功能
        self.disable_search_features()

        # 显示编辑工具栏
        self.show_edit_toolbar()

    def disable_edit_mode(self):
        """禁用文档编辑模式"""
        # 恢复只读状态
        self.content_text.config(state=tk.DISABLED)

        # 更新状态栏
        self.status_bar.config(text="编辑模式: 已禁用")

        # 重新启用搜索功能
        self.enable_search_features()

        # 隐藏编辑工具栏
        self.hide_edit_toolbar()

    def save_edited_content(self):
        """保存编辑后的内容"""
        if not self.knowledge_path:
            self.messagebox.showinfo("错误", "没有打开的文件")
            return

        try:
            # 获取编辑后的内容
            edited_content = self.content_text.get("1.0", tk.END)

            # 保存到文件
            with open(self.knowledge_path, 'w', encoding='utf-8') as file:
                file.write(edited_content)

            # 更新内存中的知识库内容
            self.knowledge_base = edited_content

            # 重新解析知识库和构建目录
            self.parse_knowledge_base()
            self.build_toc()

            # 更新状态
            self.status_bar.config(text=f"已保存文件: {os.path.basename(self.knowledge_path)}")

            # 退出编辑模式
            self.disable_edit_mode()

        except Exception as e:
            self.messagebox.showerror("保存失败", f"保存文件时出错: {str(e)}")
            self.status_bar.config(text=f"保存失败: {str(e)}")

    def cancel_editing(self):
        """取消编辑并恢复原始内容"""
        if hasattr(self, 'original_content'):
            # 恢复原始内容
            self.knowledge_base = self.original_content
            self.display_knowledge_base()

            # 删除原始内容的备份
            delattr(self, 'original_content')

        # 退出编辑模式
        self.disable_edit_mode()

        # 更新状态
        self.status_bar.config(text="已取消编辑，恢复原始内容")

    def show_edit_toolbar(self):
        """显示编辑工具栏"""
        if hasattr(self, 'edit_toolbar'):
            # 如果工具栏已存在，直接显示
            self.edit_toolbar.pack(fill=tk.X, padx=10, pady=5, before=self.main_paned)
            return

        # 创建编辑工具栏
        self.edit_toolbar = tk.Frame(self.root, bd=1, relief=tk.RAISED)
        self.edit_toolbar.pack(fill=tk.X, padx=10, pady=5, before=self.main_paned)

        # 添加保存按钮
        save_button = tk.Button(
            self.edit_toolbar,
            text="保存",
            command=self.save_edited_content,
            width=10,
            bg="#4CAF50",
            fg="white"
        )
        save_button.pack(side=tk.LEFT, padx=5, pady=5)

        # 添加取消按钮
        cancel_button = tk.Button(
            self.edit_toolbar,
            text="取消",
            command=self.cancel_editing,
            width=10,
            bg="#f44336",
            fg="white"
        )
        cancel_button.pack(side=tk.LEFT, padx=5, pady=5)

        # 添加格式化工具（针对Markdown）
        if self.knowledge_path and self.knowledge_path.lower().endswith('.md'):
            # 添加标题按钮
            h1_button = tk.Button(
                self.edit_toolbar,
                text="H1",
                command=lambda: self.insert_markdown_format("# "),
                width=3
            )
            h1_button.pack(side=tk.LEFT, padx=2, pady=5)

            h2_button = tk.Button(
                self.edit_toolbar,
                text="H2",
                command=lambda: self.insert_markdown_format("## "),
                width=3
            )
            h2_button.pack(side=tk.LEFT, padx=2, pady=5)

            h3_button = tk.Button(
                self.edit_toolbar,
                text="H3",
                command=lambda: self.insert_markdown_format("### "),
                width=3
            )
            h3_button.pack(side=tk.LEFT, padx=2, pady=5)

            # 添加列表按钮
            list_button = tk.Button(
                self.edit_toolbar,
                text="•",
                command=lambda: self.insert_markdown_format("- "),
                width=3
            )
            list_button.pack(side=tk.LEFT, padx=2, pady=5)

            # 添加格式按钮
            bold_button = tk.Button(
                self.edit_toolbar,
                text="B",
                command=lambda: self.apply_text_format("**"),
                width=3,
                font=("Arial", 9, "bold")
            )
            bold_button.pack(side=tk.LEFT, padx=2, pady=5)

            italic_button = tk.Button(
                self.edit_toolbar,
                text="I",
                command=lambda: self.apply_text_format("*"),
                width=3,
                font=("Arial", 9, "italic")
            )
            italic_button.pack(side=tk.LEFT, padx=2, pady=5)

            code_button = tk.Button(
                self.edit_toolbar,
                text="Code",
                command=lambda: self.apply_text_format("`"),
                width=5
            )
            code_button.pack(side=tk.LEFT, padx=2, pady=5)

        # 添加帮助文本
        help_label = tk.Label(
            self.edit_toolbar,
            text="编辑模式: 修改后请点击保存或取消",
            fg="#555555"
        )
        help_label.pack(side=tk.RIGHT, padx=10, pady=5)

    def hide_edit_toolbar(self):
        """隐藏编辑工具栏"""
        if hasattr(self, 'edit_toolbar'):
            self.edit_toolbar.pack_forget()

    def disable_search_features(self):
        """禁用可能干扰编辑的搜索功能"""
        # 禁用搜索按钮和语音监听
        self.search_button.config(state=tk.DISABLED)
        self.listen_button.config(state=tk.DISABLED)
        if hasattr(self, 'process_long_button'):
            self.process_long_button.config(state=tk.DISABLED)

    def enable_search_features(self):
        """重新启用搜索功能"""
        # 启用搜索按钮
        self.search_button.config(state=tk.NORMAL)

        # 如果语音识别可用，启用语音按钮
        if SPEECH_AVAILABLE and self.knowledge_base:
            self.listen_button.config(state=tk.NORMAL)
            if hasattr(self, 'process_long_button'):
                self.process_long_button.config(state=tk.NORMAL)

    def insert_markdown_format(self, prefix):
        """在当前行开头插入Markdown格式"""
        # 获取当前行信息
        current_pos = self.content_text.index(tk.INSERT)
        line_start = current_pos.split('.')[0] + '.0'

        # 在行首插入格式前缀
        self.content_text.insert(line_start, prefix)

    def apply_text_format(self, marker):
        """对选中文本应用格式"""
        # 检查是否有选中的文本
        try:
            selected_text = self.content_text.get(tk.SEL_FIRST, tk.SEL_LAST)
            start = self.content_text.index(tk.SEL_FIRST)
            end = self.content_text.index(tk.SEL_LAST)

            # 删除选中文本
            self.content_text.delete(start, end)

            # 插入带格式的文本
            self.content_text.insert(start, f"{marker}{selected_text}{marker}")
        except:
            # 如果没有选中文本，插入一对标记并将光标放在中间
            current_pos = self.content_text.index(tk.INSERT)
            self.content_text.insert(current_pos, marker + marker)
            # 将光标放在标记之间
            self.content_text.mark_set(tk.INSERT, f"{current_pos}+{len(marker)}c")

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
            self.update_tag_counts()

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
                    result = messagebox.askyesno("添加标签", f"是否将\"{query}\"添加到常用搜索标签？", parent=self.root)
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

    def setup_autocomplete(self):
        """为搜索框设置自动完成功能 - 优化版本 (修复self引用问题)"""
        # 初始化搜索历史记录
        if not hasattr(self, 'search_history'):
            self.search_history = self.load_search_history()

        # 初始化自动完成变量
        self.ac_listbox = None
        self.ac_active = False
        self.last_typed = ""
        self.suggestion_selected = False

        def show_autocomplete_dropdown(suggestions):
            """显示自动完成下拉菜单"""
            if not suggestions:
                if self.ac_listbox:
                    self.ac_listbox.destroy()
                    self.ac_listbox = None
                    self.ac_active = False
                return

            # 获取搜索框位置
            x = self.search_entry.winfo_rootx()
            y = self.search_entry.winfo_rooty() + self.search_entry.winfo_height()
            width = self.search_entry.winfo_width()

            # 创建或更新下拉框
            if not self.ac_listbox:
                self.ac_listbox = tk.Toplevel(self.root)
                self.ac_listbox.overrideredirect(True)  # 无边框窗口
                self.ac_listbox.geometry(f"{width}x{min(200, len(suggestions) * 25)}+{x}+{y}")
                self.ac_listbox.configure(bg="#ffffff", bd=1, relief=tk.SOLID)

                # 创建列表框
                listbox = tk.Listbox(
                    self.ac_listbox,
                    font=("Arial", 10),
                    selectbackground="#e0e0ff",
                    selectmode=tk.SINGLE,
                    activestyle="none",
                    exportselection=False
                )
                listbox.pack(fill=tk.BOTH, expand=True)

                # 添加滚动条
                if len(suggestions) > 8:
                    scrollbar = tk.Scrollbar(listbox)
                    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
                    listbox.config(yscrollcommand=scrollbar.set)
                    scrollbar.config(command=listbox.yview)

                # 注册事件
                listbox.bind("<ButtonRelease-1>", on_select_suggestion)
                listbox.bind("<Return>", on_select_suggestion)
                listbox.bind("<Up>", lambda e: navigate_suggestions("up"))
                listbox.bind("<Down>", lambda e: navigate_suggestions("down"))
                listbox.bind("<Escape>", lambda e: self.ac_listbox.destroy())

                self.ac_active = True
            else:
                # 更新现有下拉框
                self.ac_listbox.geometry(f"{width}x{min(200, len(suggestions) * 25)}+{x}+{y}")
                listbox = self.ac_listbox.winfo_children()[0]
                listbox.delete(0, tk.END)

            # 添加建议项
            for suggestion in suggestions:
                # 区分标签和历史
                if suggestion.startswith("🏷️ "):
                    listbox.insert(tk.END, suggestion)
                    idx = listbox.size() - 1
                    listbox.itemconfig(idx, {'bg': '#f0f8ff'})  # 标签使用淡蓝色背景
                elif suggestion.startswith("🔍 "):
                    listbox.insert(tk.END, suggestion)
                    idx = listbox.size() - 1
                    listbox.itemconfig(idx, {'bg': '#fffaf0'})  # 搜索结果使用淡黄色背景
                else:
                    listbox.insert(tk.END, suggestion)

            # 默认选中第一项
            if listbox.size() > 0:
                listbox.selection_set(0)
                listbox.see(0)

        def on_select_suggestion(event=None):
            """选择一个自动完成建议"""
            if not self.ac_listbox:
                return

            listbox = self.ac_listbox.winfo_children()[0]
            selection = listbox.curselection()

            if selection:
                selected_text = listbox.get(selection[0])

                # 去除前缀图标
                if selected_text.startswith("🏷️ ") or selected_text.startswith("🕒 ") or selected_text.startswith("🔍 "):
                    selected_text = selected_text[2:].strip()

                # 设置搜索文本
                self.search_var.set(selected_text)
                self.suggestion_selected = True

                # 关闭下拉框
                self.ac_listbox.destroy()
                self.ac_listbox = None
                self.ac_active = False

                # 执行搜索
                self.root.after(10, lambda: self.manual_search())

        def navigate_suggestions(direction):
            """使用键盘导航建议列表"""
            if not self.ac_listbox:
                return

            listbox = self.ac_listbox.winfo_children()[0]
            selection = listbox.curselection()

            if selection:
                idx = selection[0]
                listbox.selection_clear(0, tk.END)

                if direction == "up" and idx > 0:
                    listbox.selection_set(idx - 1)
                    listbox.see(idx - 1)
                elif direction == "down" and idx < listbox.size() - 1:
                    listbox.selection_set(idx + 1)
                    listbox.see(idx + 1)
                else:
                    listbox.selection_set(idx)  # 恢复选择
            elif listbox.size() > 0:
                # 如果没有选择，选择第一个或最后一个
                if direction == "up":
                    listbox.selection_set(listbox.size() - 1)
                    listbox.see(listbox.size() - 1)
                else:
                    listbox.selection_set(0)
                    listbox.see(0)

        def get_suggestions(text):
            """获取建议列表，包括标签、历史和搜索结果"""
            if not text or len(text) < 2:
                return []

            text_lower = text.lower()

            # 从标签中获取建议
            tag_suggestions = [f"🏷️ {tag}" for tag in self.tags
                               if text_lower in tag.lower()]

            # 从历史中获取建议
            history_suggestions = [f"🕒 {hist}" for hist in self.search_history
                                   if text_lower in hist.lower() and hist != text]

            # 从搜索结果中获取建议（如果已加载知识库）
            result_suggestions = []
            if self.knowledge_base:
                # 在标题中查找匹配
                for heading in self.heading_positions:
                    if text_lower in heading['text'].lower():
                        # 截断过长的标题
                        title = heading['text']
                        if len(title) > 50:
                            title = title[:47] + "..."
                        result_suggestions.append(f"🔍 {title}")
                        if len(result_suggestions) >= 5:
                            break

            # 按相关度排序
            def get_relevance(item):
                item_text = item[2:]  # 移除前缀
                item_lower = item_text.lower()

                # 排序逻辑: 完全匹配 > 开头匹配 > 包含匹配
                if item_lower == text_lower:
                    return 0
                elif item_lower.startswith(text_lower):
                    return 1
                else:
                    return 2

            # 整合并排序建议
            all_suggestions = sorted(tag_suggestions + history_suggestions[:5] + result_suggestions,
                                     key=get_relevance)

            # 限制返回数量
            return all_suggestions[:12]  # 显示最相关的12个结果

        def update_suggestions(event=None):
            """键入时更新建议"""
            # 检查是否通过选择造成的更新
            if self.suggestion_selected:
                self.suggestion_selected = False
                if self.ac_listbox:
                    self.ac_listbox.destroy()
                    self.ac_listbox = None
                    self.ac_active = False
                return

            current_text = self.search_var.get()

            # 检查文本是否变化
            if current_text == self.last_typed:
                return

            self.last_typed = current_text

            # 至少输入2个字符才显示建议
            if len(current_text) >= 2:
                suggestions = get_suggestions(current_text)
                show_autocomplete_dropdown(suggestions)
            elif self.ac_listbox:
                # 文本太短，关闭建议
                self.ac_listbox.destroy()
                self.ac_listbox = None
                self.ac_active = False

        def on_focus_out(event=None):
            """当搜索框失去焦点时处理"""
            # 使用延迟，避免点击建议项时立即关闭
            self.root.after(200, check_focus)

        def check_focus():
            """检查焦点是否在建议列表上"""
            if self.ac_listbox and self.ac_active:
                focused = self.root.focus_get()
                if focused == self.search_entry:
                    # 焦点返回到搜索框，保持下拉框
                    pass
                elif focused and str(focused).startswith(str(self.ac_listbox)):
                    # 焦点在下拉列表中，保持下拉框
                    pass
                else:
                    # 焦点在其他地方，关闭下拉框
                    self.ac_listbox.destroy()
                    self.ac_listbox = None
                    self.ac_active = False

        def on_search_key(event):
            """处理搜索框上的按键"""
            # 处理特殊键
            if event.keysym == "Down" and self.ac_active:
                # 当按下方向键时，将焦点转移到列表
                if self.ac_listbox:
                    listbox = self.ac_listbox.winfo_children()[0]
                    if listbox.size() > 0:
                        navigate_suggestions("down")
                        listbox.focus_set()
                        return "break"  # 阻止默认行为
            elif event.keysym == "Up" and self.ac_active:
                # 当按上方向键时
                if self.ac_listbox:
                    listbox = self.ac_listbox.winfo_children()[0]
                    if listbox.size() > 0:
                        navigate_suggestions("up")
                        listbox.focus_set()
                        return "break"
            elif event.keysym == "Escape" and self.ac_active:
                # 按ESC关闭下拉框
                if self.ac_listbox:
                    self.ac_listbox.destroy()
                    self.ac_listbox = None
                    self.ac_active = False
                    return "break"
            elif event.keysym == "Return" and self.ac_active:
                # 按回车选择当前项
                if self.ac_listbox:
                    listbox = self.ac_listbox.winfo_children()[0]
                    if listbox.curselection():
                        on_select_suggestion()
                        return "break"

        # 全局点击事件，用于处理点击其他区域关闭下拉框
        def global_click(event):
            if self.ac_active:
                # 检查点击区域是否在下拉框外
                if (not self.ac_listbox or
                        not (event.widget == self.search_entry or
                             str(event.widget).startswith(str(self.ac_listbox)))):
                    if self.ac_listbox:
                        self.ac_listbox.destroy()
                        self.ac_listbox = None
                        self.ac_active = False

        # 绑定事件
        self.search_entry.bind("<KeyRelease>", update_suggestions)
        self.search_entry.bind("<FocusOut>", on_focus_out)
        self.search_entry.bind("<Key>", on_search_key)
        self.root.bind("<Button-1>", global_click, add="+")  # add='+' 表示添加到现有绑定

    def load_search_history(self):
        """加载搜索历史 - 修复为类方法"""
        history_file = "search_history.txt"
        history = []

        try:
            if os.path.exists(history_file):
                with open(history_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        item = line.strip()
                        if item and item not in history:
                            history.append(item)
        except Exception as e:
            print(f"加载搜索历史失败: {e}")

        return history

    def save_search_history(self):
        """保存搜索历史 - 修复为类方法"""
        history_file = "search_history.txt"

        try:
            with open(history_file, 'w', encoding='utf-8') as f:
                for item in self.search_history:
                    f.write(f"{item}\n")
        except Exception as e:
            print(f"保存搜索历史失败: {e}")

    def add_to_search_history(self, query):
        """将查询添加到搜索历史 - 修复为类方法"""
        if not query.strip():
            return

        # 如果已存在，先移除（后面会重新添加到首位）
        if query in self.search_history:
            self.search_history.remove(query)

        # 添加到列表开头
        self.search_history.insert(0, query)

        # 限制历史记录条数
        if len(self.search_history) > 30:
            self.search_history = self.search_history[:30]

        # 保存历史
        self.save_search_history()

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
            self.toggle_listening()  # 自动关闭监听状态
            return

        # 检查选择的引擎
        engine = self.speech_engine
        self.status_bar.config(text=f"语音监听: 使用{engine}引擎")

        # Vosk引擎需要特殊处理
        if engine == "Vosk" and VOSK_AVAILABLE:
            threading.Thread(target=self.start_vosk_listening, daemon=True).start()
            return

        # 创建一个标志用于跟踪麦克风初始化
        mic_initialized = False

        try:
            with self.mic as source:
                # 调整麦克风噪声水平 - 只做一次
                self.status_bar.config(text="语音监听: 调整环境噪声...")
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                mic_initialized = True
        except Exception as e:
            self.status_bar.config(text=f"麦克风初始化错误: {e}")
            self.listening = False
            self.listen_button.config(text="开始监听", bg="green")
            return

        # 如果麦克风初始化成功，开始主循环
        if mic_initialized:
            self._run_speech_recognition_loop(engine)

    def _run_speech_recognition_loop(self, engine):
        """语音识别主循环，分离为单独的方法以提高代码可维护性"""
        recognition_errors = 0  # 跟踪连续错误
        max_errors = 5  # 最大连续错误次数

        while self.listening:
            try:
                with self.mic as source:
                    self.status_bar.config(text="语音监听: 正在听...")
                    # 使用更合理的超时设置
                    audio = self.recognizer.listen(source, timeout=5)

                    # 添加到音频缓冲区
                    self.audio_buffer.append(audio)
                    if len(self.audio_buffer) > self.max_buffer_size:
                        self.audio_buffer.pop(0)

                self.status_bar.config(text="语音监听: 正在处理...")

                # 根据引擎进行识别
                text = self._recognize_audio(audio, engine)

                if text:  # 只在成功识别文本时处理
                    recognition_errors = 0  # 重置错误计数
                    # 添加到文本历史
                    self.text_history.append(text)
                    if len(self.text_history) > 5:
                        self.text_history.pop(0)

                    # 更新搜索框并执行搜索
                    self.search_var.set(text)
                    self.root.after(0, self.search_knowledge_base, text)

            except sr.WaitTimeoutError:
                self.status_bar.config(text="语音监听: 等待输入...")
                continue
            except sr.UnknownValueError:
                recognition_errors += 1
                self.status_bar.config(text=f"语音监听: 未能识别({recognition_errors}/{max_errors})，请再说一遍...")
                if recognition_errors >= max_errors:
                    self.status_bar.config(text="多次未能识别语音，请检查麦克风设置或尝试其他引擎")
                    self.root.after(0, self.toggle_listening)  # 安全地切换状态
                    break
                continue
            except sr.RequestError as e:
                self.status_bar.config(text=f"语音识别请求错误: {e}")
                if "Google" in engine:
                    self.status_bar.config(text="语音识别错误：无法连接到Google服务。建议切换到离线引擎。")
                self.root.after(0, self.toggle_listening)  # 安全地切换状态
                break
            except Exception as e:
                self.status_bar.config(text=f"语音监听错误: {type(e).__name__}: {e}")
                time.sleep(0.5)
                recognition_errors += 1
                if recognition_errors >= max_errors:
                    self.root.after(0, self.toggle_listening)
                    break
                continue

    def _recognize_audio(self, audio, engine):
        """根据不同引擎识别音频，分离为单独方法以便于扩展和测试"""
        try:
            if engine == "Google":
                return self.recognizer.recognize_google(audio, language='zh-CN')
            elif engine == "Sphinx":
                return self.recognizer.recognize_sphinx(audio, language='zh-cn')
            else:
                # 默认回退到Google
                return self.recognizer.recognize_google(audio, language='zh-CN')
        except Exception as e:
            # 将异常向上传播，由调用方处理
            raise e

    def start_vosk_listening(self):
        """使用Vosk离线引擎进行语音识别"""
        if not VOSK_AVAILABLE:
            self.status_bar.config(text="Vosk语音识别功能不可用。请安装vosk模块")
            self.root.after(0, self.toggle_listening)  # 安全地切换状态
            return

        # 检查模型并进行初始化
        if not self._initialize_vosk_model():
            return

        # 初始化音频流
        stream, p = self._initialize_vosk_audio_stream()
        if not stream:
            return

        try:
            # 创建识别器
            recognizer = KaldiRecognizer(self.vosk_model, 16000)
            recognition_errors = 0
            max_errors = 5

            while self.listening:
                try:
                    self.status_bar.config(text="语音监听: 正在听(Vosk)...")
                    data = stream.read(4000, exception_on_overflow=False)

                    if recognizer.AcceptWaveform(data):
                        result = json.loads(recognizer.Result())
                        text = result.get("text", "")

                        if text:
                            recognition_errors = 0  # 重置错误计数
                            self.text_history.append(text)
                            if len(self.text_history) > 5:
                                self.text_history.pop(0)

                            # 更新搜索框并执行搜索
                            self.search_var.set(text)
                            self.root.after(0, self.search_knowledge_base, text)

                except Exception as e:
                    recognition_errors += 1
                    self.status_bar.config(text=f"Vosk错误: {type(e).__name__}: {str(e)}")
                    time.sleep(0.5)
                    if recognition_errors >= max_errors:
                        self.root.after(0, self.toggle_listening)
                        break

        finally:
            # 确保资源被正确释放
            if stream:
                stream.stop_stream()
                stream.close()
            if 'p' in locals() and p:
                p.terminate()
            self.status_bar.config(text="Vosk语音识别已停止")

    def _initialize_vosk_model(self):
        """初始化Vosk模型，返回是否成功"""
        model_path = os.path.join("models", "vosk-model-small-cn-0.22")
        self.status_bar.config(text="正在检查Vosk模型...")

        if not self.vosk_model:
            # 尝试加载模型
            if os.path.exists(model_path):
                try:
                    self.vosk_model = Model(model_path)
                    self.status_bar.config(text="Vosk模型加载成功")
                    return True
                except Exception as e:
                    self.status_bar.config(text=f"加载Vosk模型失败: {str(e)}")
                    self.messagebox.showerror("错误", f"加载Vosk模型失败: {str(e)}")
                    self.root.after(0, self.toggle_listening)
                    return False
            else:
                self.status_bar.config(text="Vosk模型未找到。请下载模型或切换到其他引擎。")
                self.messagebox.showwarning("警告", "Vosk模型未找到。请下载模型或切换到其他引擎。")
                self.root.after(0, self.toggle_listening)
                return False
        return True

    def _initialize_vosk_audio_stream(self):
        """初始化Vosk音频流，返回(stream, p)或(None, None)"""
        try:
            import pyaudio
            p = pyaudio.PyAudio()

            # 打开音频流
            stream = p.open(format=pyaudio.paInt16,
                            channels=1,
                            rate=16000,
                            input=True,
                            frames_per_buffer=8000)
            stream.start_stream()
            self.status_bar.config(text="Vosk音频流初始化成功")
            return stream, p
        except Exception as e:
            self.status_bar.config(text=f"初始化音频流失败: {type(e).__name__}: {str(e)}")
            self.messagebox.showerror("错误", f"初始化音频流失败: {str(e)}")
            self.root.after(0, self.toggle_listening)
            return None, None
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
        """在知识库中搜索关键词，支持模糊匹配 - 优化版"""
        start_time = time.time()  # 计时开始

        # 保存最近的搜索查询
        self.last_search_query = query

        # 清空匹配列表
        self.match_list.delete(0, tk.END)

        if not query or not self.knowledge_base:
            return

        # 更新状态
        self.status_bar.config(text="正在搜索...")

        # 从查询中提取关键词 - 这个过程可能耗时，所以我们添加进度指示
        keywords = self.extract_keywords(query)

        if not keywords:
            self.status_bar.config(text="未找到有效的搜索关键词")
            return

        # 搜索结果
        matches = []

        # 检查是否启用模糊匹配
        use_fuzzy = self.fuzzy_match_var.get()
        fuzzy_threshold = self.fuzzy_ratio

        # 如果这是一个完全匹配的标签，我们可以直接从缓存中获取结果（如果有）
        cache_key = f"{query}_{use_fuzzy}_{fuzzy_threshold}"
        if hasattr(self, 'search_cache') and cache_key in self.search_cache:
            self.current_matches = self.search_cache[cache_key]
            self._update_match_list(self.current_matches, query)
            self.status_bar.config(
                text=f"搜索完成(从缓存): 找到 {len(self.current_matches)} 个匹配 ({time.time() - start_time:.2f}秒)")
            return

        # 首先在标题中搜索（优先匹配标题）- 使用更高效的方法
        heading_matches = self._search_in_headings(keywords, use_fuzzy, fuzzy_threshold)
        matches.extend(heading_matches)

        # 如果标题匹配不够，在内容中搜索
        if len(matches) < 10:
            content_matches = self._search_in_content(keywords, use_fuzzy, fuzzy_threshold)
            matches.extend(content_matches)

        # 按匹配分数排序
        matches.sort(key=lambda x: x['score'], reverse=True)

        # 限制显示的匹配数量
        max_matches = 30
        if len(matches) > max_matches:
            matches = matches[:max_matches]

        # 更新匹配列表UI
        self._update_match_list(matches, query)

        # 高亮显示匹配项
        self.highlight_search_matches(query, matches)

        # 更新状态
        match_count = len(matches)
        search_time = time.time() - start_time
        self.status_bar.config(text=f"搜索完成: 找到 {match_count} 个匹配 ({search_time:.2f}秒)")

        # 保存匹配结果供后续使用
        self.current_matches = matches

        # 缓存结果以提高性能
        if not hasattr(self, 'search_cache'):
            self.search_cache = {}
        if len(self.search_cache) > 20:  # 限制缓存大小
            # 删除最早的缓存项
            oldest_key = next(iter(self.search_cache))
            del self.search_cache[oldest_key]
        self.search_cache[cache_key] = matches.copy()

        # 如果没有匹配项，显示提示
        if not matches:
            self.status_bar.config(text=f"搜索结果：没有找到与'{query}'匹配的内容")

    def _search_in_headings(self, keywords, use_fuzzy, fuzzy_threshold):
        """在标题中搜索关键词 - 修复版本"""
        matches = []

        # 预先创建匹配函数以避免循环中重复逻辑
        def check_match(keyword, heading_text):
            if use_fuzzy:
                try:
                    ratio = difflib.SequenceMatcher(None, keyword, heading_text).ratio() * 100
                    if ratio >= fuzzy_threshold:
                        return ratio / 100 + 1  # 更高比率给更高分数
                    elif keyword in heading_text:
                        return 1
                    else:
                        return 0  # 明确返回0表示不匹配
                except:
                    # 如果发生异常，检查直接包含
                    return 1 if keyword in heading_text else 0
            else:
                # 精确匹配
                return 1 if keyword in heading_text else 0

        # 优化处理：将标题文本预先转换为小写以避免循环内重复转换
        lowercase_headings = [(i, heading['text'].lower()) for i, heading in enumerate(self.heading_positions)]

        # 对每个关键词，找到所有匹配的标题
        for keyword in keywords:
            keyword_lower = keyword.lower()

            for idx, heading_text in lowercase_headings:
                heading = self.heading_positions[idx]
                match_score = check_match(keyword_lower, heading_text)

                # 确保match_score不是None
                if match_score is None:
                    match_score = 0

                if match_score > 0:
                    # 检查是否已经添加了这个标题
                    existing_match = next((m for m in matches if m['position'] == heading['position']), None)

                    if existing_match:
                        # 更新现有匹配项
                        existing_match['score'] += match_score
                        if keyword not in existing_match['keywords']:
                            existing_match['keywords'].append(keyword)
                    else:
                        # 添加新匹配项
                        matches.append({
                            'text': heading['text'],
                            'position': heading['position'],
                            'score': match_score,
                            'type': 'heading',
                            'keywords': [keyword]
                        })

        return matches
    def _search_in_content(self, keywords, use_fuzzy, fuzzy_threshold):
        """在内容中搜索关键词 - 分离为单独方法以提高代码清晰度"""
        matches = []

        # 将文档分成段落并预处理
        paragraphs = re.split(r'\n\s*\n', self.knowledge_base)
        processed_paragraphs = []

        # 预处理段落内容，记录它们在文档中的位置
        for para_idx, paragraph in enumerate(paragraphs):
            if not paragraph.strip():
                continue

            # 查找段落在原始文本中的位置（只对第一个段落特殊处理，提升性能）
            if para_idx == 0:
                para_pos = 0
            else:
                para_pos = self.knowledge_base.find(paragraph)

            # 预处理并存储
            processed_paragraphs.append({
                'text': paragraph,
                'lower_text': paragraph.lower(),  # 预先转换为小写
                'position': para_pos,
                'length': len(paragraph)
            })

        # 对于每个关键词，在所有段落中查找
        for keyword in keywords:
            keyword_lower = keyword.lower()

            for para in processed_paragraphs:
                para_text = para['lower_text']
                para_score = 0

                # 快速检查关键词是否在段落中
                if keyword_lower in para_text:
                    para_score = 1
                elif use_fuzzy and len(para['text']) < 500:  # 只对较短的段落使用模糊匹配
                    try:
                        ratio = difflib.SequenceMatcher(None, keyword_lower, para_text).ratio() * 100
                        if ratio >= fuzzy_threshold:
                            para_score = 0.5 + (ratio / 200)  # 权重低于直接匹配
                    except:
                        pass

                if para_score > 0:
                    # 查找最近的标题
                    nearest_heading = self._find_nearest_heading(para['position'])
                    heading_text = nearest_heading['text'] if nearest_heading else "无标题区域"

                    # 创建摘要
                    snippet = self._create_snippet(para['text'], keyword_lower)

                    # 检查是否已添加此段落
                    existing_match = next((m for m in matches
                                           if m['position'] == para['position'] and m['type'] == 'content'), None)

                    if existing_match:
                        # 更新现有匹配
                        existing_match['score'] += para_score
                        if keyword not in existing_match['keywords']:
                            existing_match['keywords'].append(keyword)
                    else:
                        # 添加新匹配
                        matches.append({
                            'text': f"{heading_text} - {snippet}",
                            'position': para['position'],
                            'score': para_score,
                            'type': 'content',
                            'keywords': [keyword]
                        })

        return matches

    def _find_nearest_heading(self, position):
        """查找给定位置前最近的标题 - 辅助函数"""
        nearest_heading = None
        nearest_distance = float('inf')

        for heading in self.heading_positions:
            if heading['position'] <= position:
                distance = position - heading['position']
                if distance < nearest_distance:
                    nearest_distance = distance
                    nearest_heading = heading

        return nearest_heading

    def _create_snippet(self, paragraph, keyword):
        """为段落创建包含关键词的摘要 - 辅助函数"""
        if len(paragraph) <= 100:
            return paragraph

        # 查找关键词的位置
        keyword_pos = paragraph.lower().find(keyword)

        if keyword_pos >= 0:
            # 创建以关键词为中心的摘要
            start_pos = max(0, keyword_pos - 40)
            end_pos = min(len(paragraph), keyword_pos + len(keyword) + 60)
            snippet = paragraph[start_pos:end_pos]

            if start_pos > 0:
                snippet = "..." + snippet
            if end_pos < len(paragraph):
                snippet = snippet + "..."
        else:
            # 如果找不到关键词，取前100个字符
            snippet = paragraph[:100] + "..."

        return snippet

    def _update_match_list(self, matches, query):
        """更新匹配列表UI - 辅助函数"""
        for match in matches:
            display_text = match['text']
            if len(display_text) > 100:
                display_text = display_text[:97] + "..."

            # 添加关键词指示器
            keywords_str = ", ".join(match['keywords'][:3])
            if len(match['keywords']) > 3:
                keywords_str += "..."

            self.match_list.insert(tk.END, f"{display_text} [关键词: {keywords_str}]")
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