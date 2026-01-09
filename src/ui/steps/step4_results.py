import customtkinter as ctk

class Step4Results(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Main container
        self.container = ctk.CTkFrame(self)
        self.container.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        self.container.grid_columnconfigure(0, weight=1)
        self.container.grid_rowconfigure(2, weight=1)

        # Title
        title = ctk.CTkLabel(self.container, text="Step 4: Results & Review", font=("Roboto", 24, "bold"))
        title.grid(row=0, column=0, pady=(20, 30))

        # Metrics Dashboard
        metrics_frame = ctk.CTkFrame(self.container)
        metrics_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=10)
        
        self.create_metric(metrics_frame, "Total Processed", "0", 0)
        self.create_metric(metrics_frame, "Successful", "0", 1, "green")
        self.create_metric(metrics_frame, "Failed", "0", 2, "red")
        self.create_metric(metrics_frame, "Skipped", "0", 3, "orange")

        # Results Grid (Simple scrollable frame)
        ctk.CTkLabel(self.container, text="Session Details:", anchor="w").grid(row=2, column=0, sticky="nw", padx=20, pady=(10,0))
        
        self.results_frame = ctk.CTkScrollableFrame(self.container, label_text="Filename | Status | Tags")
        self.results_frame.grid(row=3, column=0, sticky="nsew", padx=20, pady=10)
        
        # Placeholder Data
        for i in range(1, 6):
            self.add_result_row(f"image_{i}.jpg", "Success", "cat, animal, cute")

        # Actions
        action_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        action_frame.grid(row=4, column=0, pady=20, sticky="ew")
        
        ctk.CTkButton(action_frame, text="Open Log Folder", command=self.open_logs, fg_color="gray").pack(side="left", padx=20)
        ctk.CTkButton(action_frame, text="Export CSV", command=self.export_report).pack(side="left", padx=20)
        ctk.CTkButton(action_frame, text="New Session", command=self.new_session, fg_color="green", width=200).pack(side="right", padx=20)

    def create_metric(self, parent, label, value, col, color="white"):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=0, column=col, padx=10, pady=10, sticky="ew")
        parent.grid_columnconfigure(col, weight=1)
        
        ctk.CTkLabel(frame, text=value, font=("Roboto", 30, "bold"), text_color=color).pack()
        ctk.CTkLabel(frame, text=label, font=("Roboto", 12)).pack()

    def add_result_row(self, filename, status, tags):
        row = ctk.CTkFrame(self.results_frame)
        row.pack(fill="x", pady=2)
        
        ctk.CTkLabel(row, text=filename, width=150, anchor="w").pack(side="left", padx=5)
        
        color = "green" if status == "Success" else "red"
        ctk.CTkLabel(row, text=status, width=80, text_color=color).pack(side="left", padx=5)
        
        ctk.CTkLabel(row, text=tags, anchor="w").pack(side="left", fill="x", expand=True, padx=5)

    def open_logs(self):
        print("Opening logs...")

    def export_report(self):
        print("Exporting report...")

    def new_session(self):
        self.controller.show_step("Step1Datasource")
