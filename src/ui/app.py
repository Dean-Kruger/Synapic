import customtkinter as ctk
import logging

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initializing main application window")

        self.title("Hugging Juice Face v2")
        self.geometry("1100x700")
        
        # Set theme
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")
        self.logger.debug("UI theme configured: Dark mode with blue color theme")

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Initialize Session
        from src.core.session import Session
        from src.utils.config_manager import load_config, save_config
        
        self.logger.info("Creating new session")
        self.session = Session()
        
        self.logger.info("Loading saved configuration")
        load_config(self.session)
        
        # Save on exit
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.container = ctk.CTkFrame(self)
        self.container.grid(row=0, column=0, sticky="nsew")
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

        self.steps = {}
        
        from src.ui.steps import Step1Datasource, Step2Tagging, Step3Process, Step4Results

        self.logger.info("Creating UI steps")
        for F in (Step1Datasource, Step2Tagging, Step3Process, Step4Results):
            page_name = F.__name__
            self.logger.debug(f"Creating step: {page_name}")
            frame = F(parent=self.container, controller=self)
            self.steps[page_name] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.logger.info("Showing initial step: Step1Datasource")
        self.show_step("Step1Datasource")

    def show_step(self, page_name):
        self.logger.info(f"Navigating to step: {page_name}")
        frame = self.steps[page_name]
        frame.tkraise()
        # Trigger explicit refresh if supported (tkraise handles visibility but custom hooks might exist)
        if hasattr(frame, 'refresh_stats'):
             frame.refresh_stats()

    def on_close(self):
        self.logger.info("Application close requested - saving configuration")
        from src.utils.config_manager import save_config
        save_config(self.session)
        self.logger.info("Configuration saved, destroying window")
        self.destroy()

if __name__ == "__main__":
    app = App()
    app.mainloop()

