#!/usr/bin/env python3
"""
HTW Berlin Student Services Assistant - Database-Backed GUI
Uses PostgreSQL + pgvector instead of FAISS/pickle system
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import asyncio
import threading
from datetime import datetime
import json
import logging
import sys

# Import database-backed agents instead of legacy FAISS system
from hans_db_agents import get_database_agent, check_database_ready

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HTWAssistantDatabaseGUI:
    """Database-backed GUI for HTW Student Services Assistant"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("HTW Berlin Assistant (Database Version)")
        self.root.geometry("1000x700")
        
        # Initialize database agent
        self.db_agent = None
        self.processing = False
        
        # Setup GUI
        self.setup_gui()
        
        # Check database status
        self.check_database_status()
    
    def setup_gui(self):
        """Setup the GUI components"""
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(2, weight=1)
        
        # Title
        title_label = ttk.Label(main_frame, text="HTW Berlin Student Services Assistant", 
                               font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 10))
        
        # Database status
        self.status_frame = ttk.Frame(main_frame)
        self.status_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(self.status_frame, text="Database Status:").grid(row=0, column=0, sticky=tk.W)
        self.status_var = tk.StringVar(value="Checking database connection...")
        self.status_label = ttk.Label(self.status_frame, textvariable=self.status_var, 
                                     foreground="orange")
        self.status_label.grid(row=0, column=1, sticky=tk.W, padx=(10, 0))
        
        # Test button
        self.test_button = ttk.Button(self.status_frame, text="Test Database", 
                                     command=self.test_database, state='disabled')
        self.test_button.grid(row=0, column=2, padx=(10, 0))
        
        # Input section
        input_frame = ttk.LabelFrame(main_frame, text="Ask a Question", padding="10")
        input_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        input_frame.columnconfigure(0, weight=1)
        input_frame.rowconfigure(0, weight=1)
        
        # Text input
        self.input_text = scrolledtext.ScrolledText(input_frame, height=4, wrap=tk.WORD)
        self.input_text.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        
        # Buttons
        button_frame = ttk.Frame(input_frame)
        button_frame.grid(row=1, column=0, columnspan=2, sticky=tk.W)
        
        self.process_button = ttk.Button(button_frame, text="Generate Response", 
                                        command=self.process_query_async, state='disabled')
        self.process_button.grid(row=0, column=0, padx=(0, 10))
        
        self.clear_button = ttk.Button(button_frame, text="Clear", 
                                      command=self.clear_input)
        self.clear_button.grid(row=0, column=1)
        
        # Response section
        response_frame = ttk.LabelFrame(main_frame, text="Response", padding="10")
        response_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        response_frame.columnconfigure(0, weight=1)
        response_frame.rowconfigure(0, weight=1)
        
        # Response text
        self.response_text = scrolledtext.ScrolledText(response_frame, height=15, wrap=tk.WORD, state='disabled')
        self.response_text.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        
        # Metadata section
        metadata_frame = ttk.Frame(response_frame)
        metadata_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E))
        
        self.metadata_button = ttk.Button(metadata_frame, text="Show Details", 
                                         command=self.show_metadata, state='disabled')
        self.metadata_button.grid(row=0, column=0, padx=(0, 10))
        
        self.copy_button = ttk.Button(metadata_frame, text="Copy Response", 
                                     command=self.copy_response, state='disabled')
        self.copy_button.grid(row=0, column=1)
        
        # Status bar
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 5))
        
        # Initialize state
        self.last_response_metadata = None
        
    def check_database_status(self):
        """Check database connection and readiness"""
        def check_db():
            try:
                is_ready, message = check_database_ready()
                
                # Update UI in main thread
                self.root.after(0, self.update_database_status, is_ready, message)
                
            except Exception as e:
                self.root.after(0, self.update_database_status, False, str(e))
        
        # Run database check in background thread
        threading.Thread(target=check_db, daemon=True).start()
    
    def update_database_status(self, is_ready: bool, message: str):
        """Update database status in UI"""
        if is_ready:
            self.status_var.set(f"✅ {message}")
            self.status_label.configure(foreground="green")
            self.process_button.configure(state='normal')
            self.test_button.configure(state='normal')
            
            # Initialize database agent
            try:
                self.db_agent = get_database_agent()
                logger.info("Database agent initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize database agent: {e}")
                self.show_database_error("Failed to initialize database agent")
        else:
            self.status_var.set(f"❌ {message}")
            self.status_label.configure(foreground="red")
            self.process_button.configure(state='disabled')
            self.test_button.configure(state='normal')
            self.show_database_error(message)
    
    def show_database_error(self, message: str):
        """Show database setup instructions"""
        error_msg = f"""Database Error: {message}

To set up the database:

1. Start database: docker-compose up -d
2. Build content: python scripts/build_content_db.py
3. Restart this application

Need help? Check DOCKER_SUCCESS_SUMMARY.md"""
        
        messagebox.showerror("Database Setup Required", error_msg)
    
    def test_database(self):
        """Test database connection"""
        def test_db():
            self.root.after(0, lambda: self.status_var.set("Testing database..."))
            self.root.after(0, lambda: self.progress.start())
            
            try:
                is_ready, message = check_database_ready()
                self.root.after(0, self.update_database_status, is_ready, message)
            except Exception as e:
                self.root.after(0, self.update_database_status, False, str(e))
            finally:
                self.root.after(0, lambda: self.progress.stop())
        
        threading.Thread(target=test_db, daemon=True).start()
    
    def process_query_async(self):
        """Process query in background thread"""
        query = self.input_text.get("1.0", tk.END).strip()
        
        if not query:
            messagebox.showwarning("Input Required", "Please enter a question.")
            return
        
        if self.processing:
            return
        
        # Start processing
        self.processing = True
        self.process_button.configure(state='disabled', text="Processing...")
        self.progress.start()
        
        # Clear previous response
        self.response_text.configure(state='normal')
        self.response_text.delete("1.0", tk.END)
        self.response_text.configure(state='disabled')
        
        # Process in background
        threading.Thread(target=self.process_query_thread, args=(query,), daemon=True).start()
    
    def process_query_thread(self, query: str):
        """Process query in background thread"""
        try:
            # Use asyncio to run the async query processing
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            result = loop.run_until_complete(self.db_agent.process_query(query))
            
            # Update UI in main thread
            self.root.after(0, self.display_response, result, None)
            
        except Exception as e:
            error_msg = f"Error processing query: {str(e)}"
            logger.error(error_msg)
            self.root.after(0, self.display_response, None, error_msg)
        
        finally:
            # Reset UI state
            self.root.after(0, self.reset_processing_state)
    
    def display_response(self, result: dict = None, error: str = None):
        """Display response in UI"""
        self.response_text.configure(state='normal')
        
        if error:
            self.response_text.insert(tk.END, f"Error: {error}")
        elif result:
            # Display main response
            response = result.get('final_response', 'No response generated.')
            self.response_text.insert(tk.END, response)
            
            # Store metadata for details button
            self.last_response_metadata = result.get('metadata', {})
            self.metadata_button.configure(state='normal')
            self.copy_button.configure(state='normal')
            
            # Log successful processing
            logger.info(f"Query processed: {len(response)} chars response")
        
        self.response_text.configure(state='disabled')
    
    def reset_processing_state(self):
        """Reset UI to ready state"""
        self.processing = False
        self.process_button.configure(state='normal', text="Generate Response")
        self.progress.stop()
    
    def show_metadata(self):
        """Show detailed metadata in popup"""
        if not self.last_response_metadata:
            return
        
        metadata_window = tk.Toplevel(self.root)
        metadata_window.title("Response Details")
        metadata_window.geometry("600x400")
        
        # Metadata text
        metadata_text = scrolledtext.ScrolledText(metadata_window, wrap=tk.WORD)
        metadata_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Format metadata
        metadata_str = json.dumps(self.last_response_metadata, indent=2, default=str)
        metadata_text.insert(tk.END, metadata_str)
        metadata_text.configure(state='disabled')
    
    def clear_input(self):
        """Clear input text"""
        self.input_text.delete("1.0", tk.END)
    
    def copy_response(self):
        """Copy response to clipboard"""
        response = self.response_text.get("1.0", tk.END).strip()
        self.root.clipboard_clear()
        self.root.clipboard_append(response)
        messagebox.showinfo("Copied", "Response copied to clipboard!")
    
    def on_closing(self):
        """Handle window closing"""
        if self.db_agent:
            self.db_agent.close()
        self.root.destroy()

def main():
    """Main function"""
    root = tk.Tk()
    app = HTWAssistantDatabaseGUI(root)
    
    # Handle window closing
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    
    # Start GUI
    root.mainloop()

if __name__ == "__main__":
    main()