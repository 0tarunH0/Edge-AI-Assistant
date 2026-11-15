import queue
import threading
import customtkinter as ctk

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class HITLDialog(ctk.CTkToplevel):
    def __init__(self, master, tier: int, intent: str, command: str, on_done):
        super().__init__(master)
        self.tier = tier
        self.on_done = on_done
        self._resolved = False
        self._timer_id = None
        self.seconds_left = 15 if tier == 2 else 30

        is_tier3 = tier >= 3
        accent = "#DC2626" if is_tier3 else "#D97706"
        badge_text = (
            "TIER 3 • DESTRUCTIVE SYSTEM ACTION"
            if is_tier3
            else "TIER 2 • PRIVILEGED ACTION REVIEW"
        )

        self.title("Edge AI Assistant — Security Gate")
        self.geometry("560x390" if is_tier3 else "560x340")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.protocol("WM_DELETE_WINDOW", lambda: self._finish(False, command))

        self.update_idletasks()
        x = (self.winfo_screenwidth() - 560) // 2
        y = (self.winfo_screenheight() - 380) // 2
        self.geometry(f"+{x}+{y}")

        banner = ctk.CTkFrame(self, fg_color=accent, corner_radius=8, height=36)
        banner.pack(fill="x", padx=16, pady=(16, 10))
        ctk.CTkLabel(
            banner,
            text=badge_text,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#FFFFFF",
        ).pack(pady=6)

        ctk.CTkLabel(
            self,
            text=f"Requested Action: {intent}",
            font=ctk.CTkFont(size=13),
            anchor="w",
            wraplength=520,
        ).pack(fill="x", padx=18, pady=(0, 8))

        sub_label = (
            "Generated PowerShell Command (locked for safety):"
            if is_tier3
            else "Generated PowerShell Command (editable before execution):"
        )
        ctk.CTkLabel(
            self,
            text=sub_label,
            font=ctk.CTkFont(size=12),
            text_color="#9CA3AF",
            anchor="w",
        ).pack(fill="x", padx=18)

        self.cmd_box = ctk.CTkTextbox(
            self,
            height=110,
            font=ctk.CTkFont(family="Consolas", size=13),
            border_width=1,
            border_color=accent,
        )
        self.cmd_box.pack(fill="x", padx=18, pady=(4, 10))
        self.cmd_box.insert("1.0", command)
        if is_tier3:
            self.cmd_box.configure(state="disabled")

        if is_tier3:
            gate_frame = ctk.CTkFrame(self, fg_color="transparent")
            gate_frame.pack(fill="x", padx=18, pady=(0, 8))
            ctk.CTkLabel(
                gate_frame,
                text="Type CONFIRM to unlock:",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color="#FCA5A5",
            ).pack(side="left")

            self.confirm_entry = ctk.CTkEntry(
                gate_frame, placeholder_text="CONFIRM", width=160
            )
            self.confirm_entry.pack(side="left", padx=10)
            self.confirm_entry.bind("<KeyRelease>", self._check_confirm_text)

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=18, pady=(6, 16))

        self.timer_label = ctk.CTkLabel(
            btn_row,
            text=f"Auto-deny in {self.seconds_left}s",
            font=ctk.CTkFont(size=12),
            text_color="#9CA3AF",
        )
        self.timer_label.pack(side="left")

        self.approve_btn = ctk.CTkButton(
            btn_row,
            text="Execute Command",
            fg_color=accent,
            hover_color="#B91C1C" if is_tier3 else "#B45309",
            state="disabled" if is_tier3 else "normal",
            command=self._approve,
        )
        self.approve_btn.pack(side="right", padx=(8, 0))

        self.deny_btn = ctk.CTkButton(
            btn_row,
            text="Deny (Esc)",
            fg_color="#374151",
            hover_color="#4B5563",
            command=lambda: self._finish(False, command),
        )
        self.deny_btn.pack(side="right")

        self.bind("<Escape>", lambda _: self._finish(False, command))
        self.lift()
        self.focus_force()
        self.grab_set()
        self._tick()

    def _check_confirm_text(self, _event=None):
        typed = self.confirm_entry.get().strip()
        self.approve_btn.configure(state="normal" if typed == "CONFIRM" else "disabled")

    def _tick(self):
        if self._resolved:
            return
        if self.seconds_left <= 0:
            self._finish(False, "")
            return
        self.timer_label.configure(text=f"Auto-deny in {self.seconds_left}s")
        self.seconds_left -= 1
        self._timer_id = self.after(1000, self._tick)

    def _approve(self):
        final_cmd = self.cmd_box.get("1.0", "end-1c").strip()
        self._finish(True, final_cmd)

    def _finish(self, approved: bool, final_cmd: str):
        if self._resolved:
            return
        self._resolved = True
        if self._timer_id is not None:
            self.after_cancel(self._timer_id)
        self.grab_release()
        self.destroy()
        self.on_done(approved, final_cmd)


class HITLManager:
    def __init__(self):
        self._queue: queue.Queue = queue.Queue()
        self.root = ctk.CTk()
        self.root.withdraw()
        self._poll()

    def _poll(self):
        try:
            while True:
                tier, intent, command, event, result_box = self._queue.get_nowait()

                def on_done(approved: bool, edited_cmd: str, ev=event, box=result_box):
                    box["approved"] = approved
                    box["command"] = edited_cmd
                    ev.set()

                HITLDialog(self.root, tier, intent, command, on_done)
        except queue.Empty:
            pass
        self.root.after(50, self._poll)

    def request_approval(self, tier: int, intent: str, command: str) -> tuple[bool, str]:
        if tier in (0, 1):
            return True, command
        event = threading.Event()
        result_box = {"approved": False, "command": command}
        self._queue.put((tier, intent, command, event, result_box))
        event.wait()
        return result_box["approved"], result_box["command"]

    def run_mainloop(self):
        self.root.mainloop()