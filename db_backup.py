import os
import subprocess
from dotenv import load_dotenv
from datetime import datetime
import time


class BackupPGDB():
    def __init__(self):
        self.output_dir = os.getcwd()

        # Database connection
        self.DB_USER=os.getenv('DB_USER')
        self.DB_PASSWORD=os.getenv('DB_PASSWORD')
        self.DB_HOST=os.getenv('DB_HOST')
        self.DB_PORT=os.getenv('DB_PORT')
        self.DB_NAME = os.getenv('DB_NAME')        
        
        # Password settings
        self.env = os.environ.copy()
        self.env["PGPASSWORD"] = self.DB_PASSWORD
    
    def parse_outpath(self):
        '''Parsing of the output path and file name.'''
        
        date_str = datetime.now().strftime("%Y-%m-%d")
        filename = f"{self.DB_NAME}_backup_{date_str}.tar"
        return os.path.join(self.output_dir, filename)
        
    def create_DB_backup(self):
        '''Create Postgis DB backup using pg_dump'''
        
        # Output path
        out_path = self.parse_outpath()
        
        # Command for pg_dump backup
        cmd = [
                "pg_dump",
                "-h", self.DB_HOST,
                "-p", self.DB_PORT,
                "-U", self.DB_USER,
                "-d", self.DB_NAME,
                "-F", "t",  # custom format (komprimovaný)
                "-f", out_path                
            ]

        try:
            subprocess.run(cmd, env=self.env, check=True)
            print(f"✅ Backup created: {out_path}")
        except subprocess.CalledProcessError as e:
            print(f"❌ Backup error: {e}") 
        
        return
    
    def remove_old_files(self, days=3):
        '''Remove old deprecated backups'''
        
        now = time.time()
        for filename in os.listdir(self.output_dir):
            if filename.startswith(self.DB_NAME) and filename.endswith(".tar"):
                filepath = os.path.join(self.output_dir, filename)
                if os.path.isfile(filepath):
                    file_age = now - os.path.getmtime(filepath)
                    if file_age > days * 86400:
                        os.remove(filepath)
                        print(f"🗑️ Old file removed: {filepath}")
                        
        return

if __name__ == '__main__':
    
    load_dotenv()
    
    bpg = BackupPGDB()
    bpg.output_dir = os.path.join(os.path.dirname(__file__), '..', 'db_backups')
    
    bpg.create_DB_backup()
    bpg.remove_old_files()