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
            self.recognizer.dynamic_energy_threshold = True
            self.recognizer.energy_threshold = 300  # 降低麦克风阈值，更容易捕获声音
            self.recognizer.pause_threshold = 0.6  # 增加停顿阈值，适应更长的句子

        # Vosk相关状态
        self.vosk_model = None

        # 长对话相关
        self.audio_buffer = []
        self.max_buffer_size = 5  # 保存的音频段数量
        self.text_history = []

        # 创建界面
        self.create_ui()

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

        # 创建主内容区 - 使用PanedWindow
        self.main_paned = tk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.main_paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 左侧：匹配结果列表
        self.match_frame = tk.Frame(self.main_paned, width=250)
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
        self.toc_frame = tk.Frame(self.main_paned, width=250)
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
        self.main_paned.paneconfigure(self.match_frame, minsize=200)
        self.main_paned.paneconfigure(self.content_frame, minsize=500)
        self.main_paned.paneconfigure(self.toc_frame, minsize=200)

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

                self.heading_positions.append({
                    'text': clean_heading,
                    'position': start_pos,
                    'raw': heading_text,
                    'level': level
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

    def display_knowledge_base(self):
        """在界面中显示知识库内容"""
        # 启用文本区域进行编辑
        self.content_text.config(state=tk.NORMAL)
        self.content_text.delete(1.0, tk.END)
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
            return

        # 检查选择的引擎
        engine = self.speech_engine

        # Vosk引擎需要特殊处理
        if engine == "Vosk" and VOSK_AVAILABLE:
            self.start_vosk_listening()
            return

        with self.mic as source:
            # 调整麦克风噪声水平
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)

        while self.listening:
            try:
                with self.mic as source:
                    self.status_bar.config(text="语音监听: 正在听...")
                    # 增加短语时间限制，适应更长的句子
                    audio = self.recognizer.listen(source, timeout=3, phrase_time_limit=5)

                    # 添加到音频缓冲区用于长对话处理
                    self.audio_buffer.append(audio)
                    if len(self.audio_buffer) > self.max_buffer_size:
                        self.audio_buffer.pop(0)  # 如果缓冲区满了，移除最旧的片段

                self.status_bar.config(text="语音监听: 正在处理...")

                # 根据选择的引擎进行识别
                if engine == "Google":
                    text = self.recognizer.recognize_google(audio, language='zh-CN')
                elif engine == "Sphinx":
                    text = self.recognizer.recognize_sphinx(audio, language='zh-cn')
                else:
                    # 默认回退到Google
                    text = self.recognizer.recognize_google(audio, language='zh-CN')

                # 添加到文本历史
                self.text_history.append(text)
                if len(self.text_history) > 5:  # 保留最近5个短语
                    self.text_history.pop(0)

                # 更新搜索框
                self.search_var.set(text)

                # 在主线程中执行搜索
                self.root.after(0, self.search_knowledge_base, text)

            except sr.WaitTimeoutError:
                self.status_bar.config(text="语音监听: 等待输入...")
                continue
            except sr.UnknownValueError:
                self.status_bar.config(text="语音监听: 未能识别，请再说一遍...")
                continue
            except sr.RequestError as e:
                self.status_bar.config(text=f"语音监听错误: {e}")
                print(f"语音监听错误: {e}")
                if "Google" in engine:
                    # 如果Google识别出错，提示可以切换到离线引擎
                    # self.messagebox.showwarning("语音识别错误",
                    #                        "无法连接到Google语音识别服务。建议切换到离线引擎Sphinx或Vosk。")
                    self.status_bar.config(text=f"语音识别错误：无法连接到Google语音识别服务。建议切换到离线引擎Sphinx或Vosk。")
                self.toggle_listening()  # 停止监听
                break
            except Exception as e:
                self.status_bar.config(text=f"语音监听错误: {e}")
                print(f"语音监听错误: {e}")
                time.sleep(0.5)  # 短暂暂停防止循环过快
                continue

    def start_vosk_listening(self):
        """使用Vosk离线引擎进行语音识别"""
        if not VOSK_AVAILABLE:
            print("Vosk语音识别功能不可用。请安装vosk模块")
            # self.messagebox.showwarning("功能不可用", "Vosk语音识别功能不可用。请安装vosk模块")
            self.status_bar.config(text=f"功能不可用：Vosk语音识别功能不可用。请安装vosk模块")
            return

        if not self.vosk_model:
            # 尝试加载模型
            model_path = os.path.join("models", "vosk-model-small-cn-0.22")
            if os.path.exists(model_path):
                try:
                    self.vosk_model = Model(model_path)
                    # self.messagebox.showinfo("成功", "成功加载Vosk语音模型")
                    self.status_bar.config(text=f"成功：成功加载Vosk语音模型")
                except Exception as e:
                    print(f"加载Vosk模型失败: {str(e)}")
                    # self.messagebox.showerror("错误", f"加载Vosk模型失败: {str(e)}")
                    self.status_bar.config(text=f"错误：加载Vosk模型失败")

                    self.toggle_listening()
                    return
            else:
                print("Vosk模型未找到。请下载模型或切换到其他引擎。")
                # self.messagebox.showwarning("警告", "Vosk模型未找到。请下载模型或切换到其他引擎。")
                self.status_bar.config(text=f"警告：Vosk模型未找到。请下载模型或切换到其他引擎。")
                self.toggle_listening()
                return

        # 创建识别器
        recognizer = KaldiRecognizer(self.vosk_model, 16000)

        try:
            import pyaudio
            p = pyaudio.PyAudio()
            stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=8000)
            stream.start_stream()

            while self.listening:
                try:
                    self.status_bar.config(text="语音监听: 正在听(Vosk)...")
                    data = stream.read(4000, exception_on_overflow=False)

                    if recognizer.AcceptWaveform(data):
                        result = json.loads(recognizer.Result())
                        text = result.get("text", "")

                        if text:
                            # 添加到文本历史
                            self.text_history.append(text)
                            if len(self.text_history) > 5:
                                self.text_history.pop(0)

                            # 更新搜索框
                            self.search_var.set(text)

                            # 在主线程中执行搜索
                            self.root.after(0, self.search_knowledge_base, text)

                except Exception as e:
                    self.status_bar.config(text=f"Vosk错误: {e}")
                    print(f"Vosk错误: {e}")
                    time.sleep(0.5)

            # 停止并关闭流
            stream.stop_stream()
            stream.close()
            p.terminate()
        except Exception as e:
            print(f"初始化PyAudio失败: {str(e)}")
            # self.messagebox.showerror("错误", f"初始化PyAudio失败: {str(e)}")
            self.status_bar.config(text=f"错误：初始化PyAudio失败")
            self.toggle_listening()

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

        # 滚动到对应位置
        self.scroll_to_position(position)

        # 如果这是一个标题，同时高亮目录中的相应项目
        if match['type'] == 'heading':
            # 查找匹配的目录项
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
        """滚动内容到指定位置"""
        # 将字符位置转换为行列位置
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
                    # 使用try块防止行号超出范围
                    line_end = f"{curr_line}.end"

                    # 添加新的高亮，使用渐变效果
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
                    # 忽略超出范围的行
                    pass

        self.content_text.config(state=tk.DISABLED)

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