"""
Step 4: Results and Review UI
=============================

This module defines the final step of the tagging wizard, providing a 
comprehensive review of the processing session. It displays aggregate 
metrics and a granular list of every processed item.

Key Responsibilities:
---------------------
- Metrics Dashboard: Visualizing Success vs. Failure counts.
- Session History: Displaying a list of processed files with their status.
- External Integration: Opening the technical log file in the system default 
  text editor.
- Data Reset: Providing an entry point to restart the wizard and begin a 
  new session.

Author: Synapic Project
"""

import customtkinter as ctk
import os
import subprocess
import platform
import logging

logger = logging.getLogger(__name__)


class Step4Results(ctk.CTkFrame):
    """
    UI component for the fourth and final step of the tagging wizard.
    
    This frame serves as the post-mortem view of the tagging operations. It 
    extracts the final results from the `Session` object and presents them 
    in a human-readable format.
    
    Attributes:
        controller: The main App instance managing the wizard flow.
    """
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Main container
        self.container = ctk.CTkFrame(self)
        self.container.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        self.container.grid_columnconfigure(0, weight=1)
        self.container.grid_rowconfigure(3, weight=1)

        # Title
        title = ctk.CTkLabel(self.container, text="Step 4: Results & Review", font=("Roboto", 24, "bold"))
        title.grid(row=0, column=0, pady=(20, 30))

        # Metrics Dashboard
        self.metrics_frame = ctk.CTkFrame(self.container)
        self.metrics_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=10)
        
        self.create_metric(self.metrics_frame, "Total Processed", "0", 0)
        self.create_metric(self.metrics_frame, "Successful", "0", 1, "green")
        self.create_metric(self.metrics_frame, "Failed", "0", 2, "red")
        self.create_metric(self.metrics_frame, "Skipped", "0", 3, "orange")

        # Results Grid (Simple scrollable frame)
        ctk.CTkLabel(self.container, text="Session Details:", anchor="w").grid(row=2, column=0, sticky="nw", padx=20, pady=(10,0))
        
        self.results_frame = ctk.CTkScrollableFrame(self.container, label_text="Filename | Status | Tags | Scoring")
        self.results_frame.grid(row=3, column=0, sticky="nsew", padx=20, pady=10)

        self.action_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        self.action_frame.grid(row=4, column=0, pady=20, sticky="ew")
        self.action_frame.grid_columnconfigure(1, weight=1)
        self.open_log_btn = ctk.CTkButton(self.action_frame, text="Open Log File", command=self.open_logs, fg_color="gray")
        self.open_log_btn.grid(row=0, column=0, padx=20, sticky="w")
        self.export_btn = ctk.CTkButton(self.action_frame, text="Export CSV", command=self.export_report)
        self.export_btn.grid(row=0, column=1, padx=20, sticky="w")
        self.new_session_btn = ctk.CTkButton(self.action_frame, text="New Session", command=self.new_session, fg_color="green", width=200)
        self.new_session_btn.grid(row=0, column=2, padx=20, sticky="e")
        
    def tkraise(self, *args, **kwargs):
        super().tkraise(*args, **kwargs)
        self.refresh_stats()

    def refresh_stats(self):
        """
        Synchronize the results UI with the final data stored in the Session.
        
        This method is called every time the frame is shown (tkraise) to ensure 
        the results list is fully populated with the latest processing data.
        """
        s = self.controller.session
        
        # Update metrics
        # We need store references to metric labels or rebuild them.
        # Rebuilding is easier for this prototype.
        for widget in self.metrics_frame.winfo_children():
            widget.destroy()
            
        self.create_metric(self.metrics_frame, "Total Processed", str(s.processed_items), 0)
        self.create_metric(self.metrics_frame, "Successful", str(s.processed_items - s.failed_items), 1, "green")
        self.create_metric(self.metrics_frame, "Failed", str(s.failed_items), 2, "red")
        
        # Update Grid
        for widget in self.results_frame.winfo_children():
            widget.destroy()
            
        for res in s.results:
            self.add_result_row(
                res.get("filename", "?"),
                res.get("status", "?"),
                res.get("tags", ""),
                scoring=res.get("scoring"),
            )

    def create_metric(self, parent, label: str, value: str, col: int, color: str = "white"):
        """
        Create a styled metric card.
        
        Args:
            parent: The frame to place the metric in.
            label: Text description of the metric.
            value: The numeric value to display in large font.
            col: Grid column index.
            color: Font color for the value text.
        """
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=0, column=col, padx=10, pady=10, sticky="ew")
        parent.grid_columnconfigure(col, weight=1)
        
        ctk.CTkLabel(frame, text=value, font=("Roboto", 30, "bold"), text_color=color).pack()
        ctk.CTkLabel(frame, text=label, font=("Roboto", 12)).pack()

    # Human-readable badge text and color per scoring tier. Only tier 1
    # (logprob) is calibrated; label-confidence and semantic-JSON scores are
    # explicitly labeled as not calibrated so users never mistake them for
    # true probabilities (docs/KEYWORD_SCORING_DESIGN.md §3).
    SCORING_BADGES = {
        "logprob": ("logprob · calibrated", "green"),
        "label_confidence": ("label conf. · not calibrated", "orange"),
        "embedding": ("CLIP similarity · not calibrated", "orange"),
        "semantic_json": ("semantic JSON · not calibrated", "orange"),
        "unavailable": ("scoring unavailable", "gray"),
    }

    @classmethod
    def scoring_badge(cls, scoring):
        """Return (badge_text, color) for a result's scoring payload, or None.

        Results produced before the tier-annotated scoring contract (no
        "scoring" key) get no badge rather than a misleading default.
        """
        if not isinstance(scoring, dict):
            return None
        tier = str(scoring.get("tier", "") or "")
        if not tier:
            return None
        badge = cls.SCORING_BADGES.get(tier)
        if badge is not None:
            return badge
        # Unknown tier from a newer payload: show the raw tier honestly.
        return (tier, "gray")

    def add_result_row(self, filename, status, tags, scoring=None):
        row = ctk.CTkFrame(self.results_frame)
        row.pack(fill="x", pady=2)
        row.grid_columnconfigure(2, weight=1)
        
        ctk.CTkLabel(row, text=filename, width=150, anchor="w").grid(row=0, column=0, padx=5, sticky="w")
        
        color = "green" if status == "Success" else "red"
        ctk.CTkLabel(row, text=status, width=80, text_color=color).grid(row=0, column=1, padx=5, sticky="w")
        
        ctk.CTkLabel(row, text=tags, anchor="w", justify="left", wraplength=700).grid(row=0, column=2, padx=5, sticky="ew")

        badge = self.scoring_badge(scoring)
        if badge is not None:
            badge_text, badge_color = badge
            ctk.CTkLabel(
                row,
                text=badge_text,
                width=220,
                anchor="w",
                font=("Roboto", 11),
                text_color=badge_color,
            ).grid(row=0, column=3, padx=(5, 15), sticky="w")

    def open_logs(self):
        """Open the detailed log file (synapic.log)."""
        from src.utils.logger import LOG_DIR
        log_file = LOG_DIR / "synapic.log"
        
        try:
            if not log_file.exists():
                logger.warning(f"Log file does not exist: {log_file}")
                # Fallback to directory
                if LOG_DIR.exists():
                     self._open_path(LOG_DIR)
                return

            self._open_path(log_file)
            logger.info(f"Opened log file: {log_file}")

        except Exception as e:
            logger.error(f"Failed to open log file: {e}")

    def _open_path(self, path):
        """Helper to open file or folder."""
        system = platform.system()
        if system == 'Windows':
            os.startfile(path)
        elif system == 'Darwin':  # macOS
            subprocess.run(['open', str(path)])
        else:  # Linux
            subprocess.run(['xdg-open', str(path)])

    def export_report(self):
        """
        Export the current session results to a CSV file.

        Prompts the user for a destination path, then writes a summary block
        (total / successful / failed) followed by a header row and one row per
        processed item (filename, status, tags). The file is opened with UTF-8
        encoding and a BOM so Excel on Windows renders non-ASCII tag text
        correctly.

        Exceptions are surfaced via a messagebox rather than silently failing,
        so the user always knows whether the export succeeded.
        """
        import csv
        from tkinter import filedialog, messagebox

        session = self.controller.session
        try:
            file_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                title="Export Session Results",
            )
            if not file_path:
                logger.info("Report export cancelled by user")
                return

            with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(["Total Processed", session.processed_items])
                writer.writerow([
                    "Successful",
                    session.processed_items - session.failed_items,
                ])
                writer.writerow(["Failed", session.failed_items])
                writer.writerow([])
                writer.writerow([
                    "Filename",
                    "Status",
                    "Tags",
                    "Scoring Tier",
                    "Calibrated",
                    "Probabilities",
                ])
                for res in session.results:
                    scoring = res.get("scoring")
                    if not isinstance(scoring, dict):
                        scoring = {}
                    tier = scoring.get("tier", "")
                    calibrated = scoring.get("calibrated")
                    calibrated_text = (
                        "" if calibrated is None else ("yes" if calibrated else "no")
                    )
                    writer.writerow([
                        res.get("filename", "?"),
                        res.get("status", "?"),
                        res.get("tags", ""),
                        tier,
                        calibrated_text,
                        self._format_probabilities(res.get("probabilities")),
                    ])

            logger.info(f"Report exported to {file_path}")
            messagebox.showinfo("Export Complete", f"Report saved to:\n{file_path}")
        except Exception as e:
            logger.error(f"Failed to export report: {e}", exc_info=True)
            messagebox.showerror("Export Failed", f"Could not export report:\n{e}")
    @staticmethod
    def _format_probabilities(probabilities):
        """Format a result's score map as "A=0.700; B=0.200" for CSV export.

        Entries without a score map (e.g. results from runs with scoring
        disabled) export as an empty cell. Non-float values are printed
        as-is rather than crashing the export.
        """
        if not isinstance(probabilities, dict) or not probabilities:
            return ""
        parts = []
        for keyword, score in probabilities.items():
            try:
                parts.append(f"{keyword}={float(score):.3f}")
            except (TypeError, ValueError):
                parts.append(f"{keyword}={score}")
        return "; ".join(parts)

    def new_session(self):
        self.controller.show_step("Step1Datasource")
