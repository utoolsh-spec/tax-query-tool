# coding=utf-8
"""
上海税务状态查询工具 - GUI版本
左右布局：左边输入信用代码，右边显示查询结果
"""

import requests
import time
import re
import random
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from datetime import datetime

# 修复后的 ddddocr 导入
import ddddocr


class TaxQueryApp:
    def __init__(self, root):
        self.root = root
        self.root.title("上海税务状态查询工具")
        self.root.geometry("1200x700")
        self.root.minsize(1000, 600)
        
        # 查询控制标志
        self.is_running = False
        self.query_thread = None
        self.stop_event = threading.Event()
        
        # 初始化 OCR（只初始化一次）
        self.ocr = None
        
        self.setup_ui()
    
    def setup_ui(self):
        """设置GUI界面"""
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置grid权重，使窗口可缩放
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1, minsize=350)
        main_frame.columnconfigure(1, weight=2, minsize=700)
        main_frame.rowconfigure(1, weight=1)
        
        # ===== 标题 =====
        title_label = ttk.Label(
            main_frame, 
            text="上海税务状态批量查询工具", 
            font=("Arial", 16, "bold")
        )
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 10))
        
        # ===== 左侧面板：输入区域 =====
        left_frame = ttk.LabelFrame(main_frame, text="信用代码输入", padding="10")
        left_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))
        left_frame.columnconfigure(0, weight=1)
        left_frame.rowconfigure(1, weight=1)
        
        # 输入提示
        hint_label = ttk.Label(
            left_frame, 
            text="请输入统一社会信用代码/税号\n每行一个：",
            foreground="gray"
        )
        hint_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        
        # 输入文本框
        self.input_text = scrolledtext.ScrolledText(
            left_frame, 
            width=40, 
            height=35,
            font=("Consolas", 11)
        )
        self.input_text.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # ===== 设置区域 =====
        settings_frame = ttk.LabelFrame(left_frame, text="查询设置", padding="5")
        settings_frame.grid(row=2, column=0, pady=(10, 0), sticky=(tk.W, tk.E))
        
        # 间隔控制
        self.enable_delay = tk.BooleanVar(value=False)
        self.delay_checkbox = ttk.Checkbutton(
            settings_frame, 
            text="启用查询间隔（1-5秒随机）",
            variable=self.enable_delay
        )
        self.delay_checkbox.pack(anchor=tk.W, pady=2)
        
        # 按钮区域
        btn_frame = ttk.Frame(left_frame)
        btn_frame.grid(row=3, column=0, pady=(10, 0), sticky=(tk.W, tk.E))
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)
        
        self.start_btn = ttk.Button(
            btn_frame, 
            text="▶ 开始查询", 
            command=self.start_query,
            style="Accent.TButton"
        )
        self.start_btn.grid(row=0, column=0, padx=(0, 5), sticky=(tk.W, tk.E))
        
        self.stop_btn = ttk.Button(
            btn_frame, 
            text="⏹ 停止查询", 
            command=self.stop_query,
            state=tk.DISABLED
        )
        self.stop_btn.grid(row=0, column=1, padx=(5, 0), sticky=(tk.W, tk.E))
        
        # 清空按钮
        self.clear_btn = ttk.Button(
            left_frame, 
            text="🗑 清空输入", 
            command=self.clear_input
        )
        self.clear_btn.grid(row=4, column=0, pady=(5, 0), sticky=(tk.W, tk.E))
        
        # 统计信息
        self.stats_label = ttk.Label(left_frame, text="待查询: 0 个")
        self.stats_label.grid(row=5, column=0, pady=(10, 0), sticky=tk.W)
        
        # 绑定输入变化事件
        self.input_text.bind("<KeyRelease>", self.update_stats)
        
        # ===== 右侧面板：结果显示（仅表格） =====
        right_frame = ttk.LabelFrame(main_frame, text="查询结果", padding="10")
        right_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(5, 0))
        right_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(0, weight=1)
        
        # ===== 表格显示区域 =====
        table_frame = ttk.Frame(right_frame)
        table_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
        
        # 创建 Treeview 表格
        columns = ('序号', '信用代码', '查询结果', '纳税人状态', '纳税人名称')
        self.result_table = ttk.Treeview(table_frame, columns=columns, show='headings')
        
        # 设置列标题和宽度
        self.result_table.heading('序号', text='序号')
        self.result_table.heading('信用代码', text='信用代码')
        self.result_table.heading('查询结果', text='查询结果')
        self.result_table.heading('纳税人状态', text='纳税人状态')
        self.result_table.heading('纳税人名称', text='纳税人名称')
        
        self.result_table.column('序号', width=50, anchor='center')
        self.result_table.column('信用代码', width=180, anchor='center')
        self.result_table.column('查询结果', width=100, anchor='center')
        self.result_table.column('纳税人状态', width=100, anchor='center')
        self.result_table.column('纳税人名称', width=250, anchor='w')
        
        # 添加滚动条
        table_scroll_y = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.result_table.yview)
        table_scroll_x = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.result_table.xview)
        self.result_table.configure(yscrollcommand=table_scroll_y.set, xscrollcommand=table_scroll_x.set)
        
        self.result_table.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        table_scroll_y.grid(row=0, column=1, sticky=(tk.N, tk.S))
        table_scroll_x.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
        # 配置表格标签样式（用于颜色标记）
        self.result_table.tag_configure('success', foreground='green')
        self.result_table.tag_configure('not_found', foreground='orange')
        self.result_table.tag_configure('error', foreground='red')
        self.result_table.tag_configure('normal', foreground='black')
        
        # 结果操作按钮
        result_btn_frame = ttk.Frame(right_frame)
        result_btn_frame.grid(row=1, column=0, pady=(10, 0), sticky=(tk.W, tk.E))
        result_btn_frame.columnconfigure(0, weight=1)
        result_btn_frame.columnconfigure(1, weight=1)
        result_btn_frame.columnconfigure(2, weight=1)
        result_btn_frame.columnconfigure(3, weight=1)
        
        self.copy_btn = ttk.Button(
            result_btn_frame, 
            text="📋 复制当前页", 
            command=self.copy_results
        )
        self.copy_btn.grid(row=0, column=0, padx=(0, 5), sticky=(tk.W, tk.E))
        
        self.export_btn = ttk.Button(
            result_btn_frame, 
            text="💾 导出结果", 
            command=self.export_results
        )
        self.export_btn.grid(row=0, column=1, padx=5, sticky=(tk.W, tk.E))
        
        self.clear_result_btn = ttk.Button(
            result_btn_frame, 
            text="🗑 清空结果", 
            command=self.clear_results
        )
        self.clear_result_btn.grid(row=0, column=2, padx=5, sticky=(tk.W, tk.E))
        
        self.retry_btn = ttk.Button(
            result_btn_frame, 
            text="🔄 重试错误项", 
            command=self.retry_failed
        )
        self.retry_btn.grid(row=0, column=3, padx=(5, 0), sticky=(tk.W, tk.E))
        
        # ===== 底部状态栏 =====
        status_frame = ttk.Frame(main_frame)
        status_frame.grid(row=2, column=0, columnspan=2, pady=(10, 0), sticky=(tk.W, tk.E))
        
        self.status_label = ttk.Label(status_frame, text="就绪")
        self.status_label.pack(side=tk.LEFT)
        
        self.progress_label = ttk.Label(status_frame, text="")
        self.progress_label.pack(side=tk.RIGHT)
        
        # 设置样式
        style = ttk.Style()
        style.configure("Accent.TButton", font=("Arial", 10, "bold"))
    
    def update_stats(self, event=None):
        """更新统计信息"""
        content = self.input_text.get("1.0", tk.END).strip()
        count = len([line for line in content.split('\n') if line.strip()])
        self.stats_label.config(text=f"待查询: {count} 个")
    
    def log(self, message, tag="info"):
        """添加日志到状态栏（线程安全）"""
        def append_log():
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.status_label.config(text=f"[{timestamp}] {message}")

        if threading.current_thread() is threading.main_thread():
            append_log()
        else:
            self.root.after(0, append_log)
    
    def log_result(self, code, result_data):
        """记录查询结果（仅更新表格，不显示详情）"""
        # 这个方法现在只作为兼容保留，实际显示由 update_summary 处理
        pass
    
    def update_summary(self, results):
        """更新表格显示"""
        def update():
            # 清空现有数据
            for item in self.result_table.get_children():
                self.result_table.delete(item)
            
            # 填充表格数据
            for idx, result in enumerate(results, 1):
                code = result.get("code", "未知")
                status = result.get("status", "未知")
                name = result.get("name", "")
                nsr_status = result.get("nsr_status", "")  # 纳税人状态
                
                # 确定查询结果列的显示内容和标签
                if status == "成功":
                    display_status = "查询成功"
                    tag = 'success'
                elif status == "没有查到":
                    display_status = "没有查到"
                    tag = 'not_found'
                elif status in ["查询失败", "异常", "未知错误"]:
                    display_status = "查询错误"
                    tag = 'error'
                else:
                    display_status = status
                    tag = 'normal'
                
                # 插入表格行
                self.result_table.insert('', tk.END, values=(
                    idx, 
                    code, 
                    display_status, 
                    nsr_status if nsr_status else ("-" if status == "成功" else ""),
                    name
                ), tags=(tag,))
        
        if threading.current_thread() is threading.main_thread():
            update()
        else:
            self.root.after(0, update)
    
    def clear_input(self):
        """清空输入"""
        if messagebox.askyesno("确认", "确定要清空所有输入吗？"):
            self.input_text.delete("1.0", tk.END)
            self.update_stats()
    
    def clear_results(self):
        """清空结果"""
        if messagebox.askyesno("确认", "确定要清空所有结果吗？"):
            # 清空表格
            for item in self.result_table.get_children():
                self.result_table.delete(item)
            
            self.query_results = []
    
    def copy_results(self):
        """复制表格结果到剪贴板"""
        if not hasattr(self, 'query_results') or not self.query_results:
            messagebox.showwarning("警告", "没有可复制的结果！")
            return
        
        lines = []
        lines.append("序号\t信用代码\t查询结果\t纳税人状态\t纳税人名称")
        
        for idx, result in enumerate(self.query_results, 1):
            status = result.get('status', '')
            if status == "成功":
                display_status = "查询成功"
            elif status == "没有查到":
                display_status = "没有查到"
            elif status in ["查询失败", "异常", "未知错误"]:
                display_status = "查询错误"
            else:
                display_status = status
            
            nsr_status = result.get('nsr_status', '')
            if not nsr_status and status == "成功":
                nsr_status = "-"
            
            line = f"{idx}\t{result.get('code', '')}\t{display_status}\t{nsr_status}\t{result.get('name', '')}"
            lines.append(line)
        
        content = "\n".join(lines)
        self.root.clipboard_clear()
        self.root.clipboard_append(content)
        messagebox.showinfo("提示", "表格结果已复制到剪贴板！")
    
    def export_results(self):
        """导出结果到文件"""
        if not hasattr(self, 'query_results') or not self.query_results:
            messagebox.showwarning("警告", "没有可导出的结果！")
            return
        
        from tkinter import filedialog
        import csv
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV文件", "*.csv"), ("文本文件", "*.txt"), ("所有文件", "*.*")],
            initialfile=f"查询结果_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        
        if filename:
            try:
                with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    writer.writerow(['信用代码', '查询结果', '纳税人状态', '纳税人名称', '税种', '所属期', '金额', '提示信息'])
                    
                    for result in self.query_results:
                        status = result.get('status', '')
                        # 转换状态显示
                        if status == "成功":
                            display_status = "查询成功"
                        elif status == "没有查到":
                            display_status = "没有查到"
                        elif status in ["查询失败", "异常", "未知错误"]:
                            display_status = "查询错误"
                        else:
                            display_status = status
                        
                        writer.writerow([
                            result.get('code', ''),
                            display_status,
                            result.get('nsr_status', ''),  # 纳税人状态
                            result.get('name', ''),
                            result.get('tax_type', ''),
                            result.get('period', ''),
                            result.get('amount', ''),
                            result.get('message', '')
                        ])
                
                messagebox.showinfo("成功", f"结果已导出到:\n{filename}")
            except Exception as e:
                messagebox.showerror("错误", f"导出失败: {e}")
    
    def retry_failed(self):
        """重新查询失败的项"""
        if not hasattr(self, 'query_results') or not self.query_results:
            messagebox.showwarning("警告", "没有可重试的查询记录！")
            return
        
        # 找出查询失败的项
        failed_items = [r for r in self.query_results if r.get("status") in ["查询失败", "异常", "未知错误"]]
        
        if not failed_items:
            messagebox.showinfo("提示", "没有查询错误的项目需要重试！")
            return
        
        failed_codes = [r.get("code") for r in failed_items]
        
        if messagebox.askyesno("确认", f"发现 {len(failed_codes)} 个查询错误的项目，是否重新查询？"):
            # 从结果列表中移除失败的项
            self.query_results = [r for r in self.query_results if r.get("status") not in ["查询失败", "异常", "未知错误"]]
            
            # 更新表格显示（移除错误项）
            self.update_summary(self.query_results)
            
            # 启动重试查询
            self.is_running = True
            self.stop_event.clear()
            self.start_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)
            self.retry_btn.config(state=tk.DISABLED)
            self.input_text.config(state=tk.DISABLED)
            
            # 启动查询线程
            self.status_label.config(text="正在重新查询错误项...")
            self.query_thread = threading.Thread(target=self.query_worker, args=(failed_codes,), daemon=True)
            self.query_thread.start()
    
    def start_query(self):
        """开始批量查询"""
        # 获取输入内容
        content = self.input_text.get("1.0", tk.END).strip()
        if not content:
            messagebox.showwarning("警告", "请输入至少一个信用代码！")
            return
        
        codes = [line.strip() for line in content.split('\n') if line.strip()]
        if not codes:
            messagebox.showwarning("警告", "没有有效的信用代码！")
            return
        
        # 检查是否有重复的代码
        unique_codes = list(dict.fromkeys(codes))
        if len(unique_codes) < len(codes):
            if messagebox.askyesno("提示", f"检测到重复代码，是否去重后查询？\n原数量: {len(codes)} 个，去重后: {len(unique_codes)} 个"):
                codes = unique_codes
                # 更新输入框
                self.input_text.delete("1.0", tk.END)
                self.input_text.insert("1.0", '\n'.join(codes))
                self.update_stats()
            else:
                return
        
        # 清空之前的结果
        self.query_results = []
        # 清空表格
        for item in self.result_table.get_children():
            self.result_table.delete(item)
        
        # 更新UI状态
        self.is_running = True
        self.stop_event.clear()
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.input_text.config(state=tk.DISABLED)
        self.enable_delay_checkbox = self.delay_checkbox
        
        # 初始化OCR
        self.status_label.config(text="正在初始化 OCR...")
        self.root.update()
        
        try:
            if self.ocr is None:
                self.ocr = ddddocr.DdddOcr()
        except Exception as e:
            messagebox.showerror("错误", f"OCR初始化失败: {e}")
            self.reset_ui()
            return
        
        # 启动查询线程
        self.status_label.config(text="正在查询...")
        self.query_thread = threading.Thread(target=self.query_worker, args=(codes,), daemon=True)
        self.query_thread.start()
    
    def stop_query(self):
        """停止查询"""
        if self.is_running:
            self.is_running = False
            self.stop_event.set()
            self.status_label.config(text="正在停止...")
            self.log("用户请求停止查询", "warning")
    
    def reset_ui(self):
        """重置UI状态"""
        self.is_running = False
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.retry_btn.config(state=tk.NORMAL)
        self.input_text.config(state=tk.NORMAL)
        self.status_label.config(text="就绪")
        self.progress_label.config(text="")
    
    def query_worker(self, codes):
        """查询工作线程"""
        total = len(codes)
        
        self.log(f"开始批量查询，共 {total} 个信用代码")
        
        for idx, code in enumerate(codes, 1):
            if self.stop_event.is_set():
                self.log("查询已停止", "warning")
                break
            
            # 更新进度
            self.root.after(0, lambda i=idx, t=total: self.progress_label.config(
                text=f"进度: {i}/{t} ({i*100//t}%)"
            ))
            
            self.log(f"[{idx}/{total}] 正在查询: {code}")
            
            result_data = {"code": code, "status": "失败", "message": ""}
            
            try:
                result = self.query_single(code)
                
                if result == "NOT_FOUND":
                    result_data["status"] = "没有查到"
                    result_data["message"] = "系统中没有该纳税人的相关信息"
                    
                elif result == "FAILED":
                    result_data["status"] = "查询失败"
                    result_data["message"] = "查询过程中发生错误"
                    
                elif result and isinstance(result, dict):
                    result_data.update(result)
                    result_data["status"] = "成功"
                    
                else:
                    result_data["status"] = "未知错误"
                    result_data["message"] = "返回数据格式异常"
                    
            except Exception as e:
                result_data["status"] = "异常"
                result_data["message"] = str(e)
            
            # 记录结果
            self.query_results.append(result_data)
            self.update_summary(self.query_results)
            
            # 间隔控制（仅在启用时）
            if idx < total and not self.stop_event.is_set() and self.enable_delay.get():
                delay = random.uniform(1, 5)
                for _ in range(int(delay * 10)):
                    if self.stop_event.is_set():
                        break
                    time.sleep(0.1)
        
        # 查询完成
        success = sum(1 for r in self.query_results if r.get("status") == "成功")
        not_found = sum(1 for r in self.query_results if r.get("status") == "没有查到")
        failed = len(self.query_results) - success - not_found
        self.log(f"查询完成！成功:{success} 没有查到:{not_found} 错误:{failed}")
        
        self.root.after(0, self.reset_ui)
    
    def query_single(self, shhtym):
        """
        查询单个信用代码
        返回: 解析后的结果字典, "NOT_FOUND", 或 "FAILED"
        """
        session = requests.Session()
        
        headers = {
            'Host': 'etax.shanghai.chinatax.gov.cn',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Origin': 'http://etax.shanghai.chinatax.gov.cn',
            'Referer': 'http://etax.shanghai.chinatax.gov.cn/newxbwt/wzfw/YhscxCtrl-yhsCx.pfv',
            'Connection': 'keep-alive'
        }
        
        max_retries = 3
        
        for attempt in range(max_retries):
            if self.stop_event.is_set():
                return "FAILED"
            
            try:
                # 获取验证码
                timestamp = int(time.time() * 1000)
                captcha_url = f"http://etax.shanghai.chinatax.gov.cn/newxbwt/servlet/GetshowimgSmall?{timestamp}"
                
                captcha_resp = session.get(captcha_url, headers=headers, timeout=10)
                captcha_resp.raise_for_status()
                image_bytes = captcha_resp.content
                
                # 识别验证码
                captcha_text = self.ocr.predict(image_bytes)
                
                if not captcha_text or len(captcha_text) != 4:
                    continue
                
                # 提交查询
                query_url = "http://etax.shanghai.chinatax.gov.cn/newxbwt/wzfw/YhscxCtrl-yhsCx.pfv"
                data = {
                    'shhtym': shhtym,
                    'yzm': captcha_text
                }
                
                query_resp = session.post(query_url, headers=headers, data=data, timeout=10)
                query_resp.raise_for_status()
                html_content = query_resp.text
                
                # 解析结果
                if "var msg='验证码输入错误';" in html_content:
                    continue
                    
                if "没有查到该纳税人的相关信息" in html_content:
                    return "NOT_FOUND"
                
                # 查询成功，解析HTML内容
                return self.parse_result(html_content)
                
            except Exception as e:
                if attempt == max_retries - 1:
                    raise e
                time.sleep(1)
        
        return "FAILED"
    
    def parse_result(self, html_content):
        """解析查询结果HTML，提取有用信息"""
        result = {
            "name": "",
            "nsr_status": "",  # 纳税人状态（如：注销、正常等）
            "tax_type": "",
            "tax_status": "",
            "period": "",
            "amount": "",
            "message": ""
        }
        
        try:
            # 尝试从 input 标签中提取纳税人名称
            # 格式：<input ... value="纳税人名称"/>
            name_input_match = re.search(r'纳税人名称[：:]\s*</td>\s*<td[^>]*>\s*<input[^>]*value="([^"]*)"', html_content, re.DOTALL)
            if name_input_match:
                result["name"] = name_input_match.group(1).strip()
            else:
                # 备用：直接匹配文本
                name_match = re.search(r'纳税人名称[：:]\s*([^<\n]+)', html_content)
                if name_match:
                    result["name"] = name_match.group(1).strip()
            
            # 尝试从 input 标签中提取纳税人状态
            # 格式：<input ... value="注销"/>
            nsr_status_match = re.search(r'纳税人状态[：:]\s*</td>\s*<td[^>]*>\s*<input[^>]*value="([^"]*)"', html_content, re.DOTALL)
            if nsr_status_match:
                result["nsr_status"] = nsr_status_match.group(1).strip()
            else:
                # 备用：直接匹配文本
                nsr_status_text = re.search(r'纳税人状态[：:]\s*([^<\n]+)', html_content)
                if nsr_status_text:
                    result["nsr_status"] = nsr_status_text.group(1).strip()
            
            # 尝试提取统一社会信用代码
            shxydm_match = re.search(r'统一社会信用代码[：:]\s*</td>\s*<td[^>]*>\s*<input[^>]*value="([^"]*)"', html_content, re.DOTALL)
            if shxydm_match:
                result["shxydm"] = shxydm_match.group(1).strip()
            
            # 尝试提取纳税人识别号
            nsrsbh_match = re.search(r'纳税人识别号[：:]\s*</td>\s*<td[^>]*>\s*<input[^>]*value="([^"]*)"', html_content, re.DOTALL)
            if nsrsbh_match:
                result["nsrsbh"] = nsrsbh_match.group(1).strip()
            
            # 尝试提取税种
            tax_type_match = re.search(r'税种[：:]\s*([^<\n]+)', html_content)
            if tax_type_match:
                result["tax_type"] = tax_type_match.group(1).strip()
            
            # 尝试提取纳税状态
            status_match = re.search(r'(?:纳税状态|申报状态|缴款状态)[：:]\s*([^<\n]+)', html_content)
            if status_match:
                result["tax_status"] = status_match.group(1).strip()
            
            # 尝试提取所属期
            period_match = re.search(r'所属期[：:]\s*([^<\n]+)', html_content)
            if period_match:
                result["period"] = period_match.group(1).strip()
            
            # 尝试提取金额
            amount_match = re.search(r'(?:金额|税额)[：:]\s*([^<\n]+)', html_content)
            if amount_match:
                result["amount"] = amount_match.group(1).strip()
            
            # 如果没有提取到具体信息，保存一段HTML作为参考
            if not any([result["name"], result["nsr_status"]]):
                # 尝试查找表格内容
                table_match = re.search(r'<table[^>]*>.*?</table>', html_content, re.DOTALL)
                if table_match:
                    result["message"] = "请查看详细页面"
                else:
                    result["message"] = "查询成功，但未解析到具体信息"
                    
        except Exception as e:
            result["message"] = f"解析结果时出错: {e}"
        
        return result


def main():
    root = tk.Tk()
    app = TaxQueryApp(root)
    
    # 设置窗口关闭处理
    def on_closing():
        if app.is_running:
            if messagebox.askokcancel("确认", "查询正在进行中，确定要退出吗？"):
                app.stop_query()
                root.after(500, root.destroy)
        else:
            root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    
    # 启动主循环
    root.mainloop()


if __name__ == '__main__':
    main()
