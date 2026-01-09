import customtkinter as ctk

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Hugging Juice Face v2")
        self.geometry("1100x700")
        
        # Set theme
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Initialize Session
        from src.core.session import Session
        self.session = Session()

        self.container = ctk.CTkFrame(self)
        self.container.grid(row=0, column=0, sticky="nsew")
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

        self.steps = {}
        
        from src.ui.steps import Step1Datasource, Step2Tagging, Step3Process, Step4Results

        for F in (Step1Datasource, Step2Tagging, Step3Process, Step4Results):
            page_name = F.__name__
            frame = F(parent=self.container, controller=self)
            self.steps[page_name] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.show_step("Step1Datasource")

    def show_step(self, page_name):
        frame = self.steps[page_name]
        frame.tkraise()

if __name__ == "__main__":
    app = App()
    app.mainloop()
