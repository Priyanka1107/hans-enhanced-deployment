import json
import re
import os
from datetime import datetime

class HTWDataCleaner:
    """
    Cleans the scraped HTW data by fixing misidentified contacts and other issues
    """
    
    def __init__(self, data_dir='htw_student_data'):
        self.data_dir = data_dir
        self.stats = {
            'removed_fake_phones': 0,
            'removed_fake_emails': 0,
            'fixed_encoding': 0,
            'cleaned_dates': 0,
            'total_pages_processed': 0
        }
        
        # Patterns for validation
        self.date_patterns = [
            re.compile(r'^\d{1,2}\.\d{1,2}\.\d{4}'),  # DD.MM.YYYY
            re.compile(r'^\d{1,2}/\d{1,2}/\d{4}'),    # DD/MM/YYYY
            re.compile(r'^\d{4}-\d{2}-\d{2}'),         # YYYY-MM-DD
            re.compile(r'^\d{1,2}\.\d{1,2}\.\d{2}'),   # DD.MM.YY
        ]
        
        # Valid phone patterns (German numbers)
        self.valid_phone_patterns = [
            re.compile(r'^[\+]?49[\s\-]?[\(]?\d{2,4}[\)]?[\s\-]?\d{3,10}'),  # +49 or German international
            re.compile(r'^[\(]?0\d{2,4}[\)]?[\s\-]?\d{3,10}'),                # German with area code
            re.compile(r'^\d{3,5}[\s\-]?\d{4,8}$'),                           # Local numbers
        ]
        
        # Encoding fixes
        self.encoding_fixes = {
            'â€™': "'",
            'â€œ': '"',
            'â€': '"',
            'â€"': '–',
            'â€"': '—',
            'Ã¼': 'ü',
            'Ã¤': 'ä',
            'Ã¶': 'ö',
            'ÃŸ': 'ß',
            'Ã„': 'Ä',
            'Ã–': 'Ö',
            'Ãœ': 'Ü',
            'Â': '',
            'Ã©': 'é',
            'Ã¨': 'è',
            'Ã ': 'à',
        }
    
    def is_date(self, value):
        """Check if a value is actually a date"""
        for pattern in self.date_patterns:
            if pattern.match(value.strip()):
                return True
        return False
    
    def is_valid_phone(self, value):
        """Check if a value is a valid phone number"""
        # Remove spaces and common separators for checking
        cleaned = value.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
        
        # Must have at least 10 digits
        digit_count = sum(c.isdigit() for c in cleaned)
        if digit_count < 10 or digit_count > 15:
            return False
        
        # Check against valid patterns
        for pattern in self.valid_phone_patterns:
            if pattern.match(value):
                return True
        
        return False
    
    def is_valid_email(self, value):
        """Check if a value is a valid email"""
        email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
        return bool(email_pattern.match(value.strip()))
    
    def fix_encoding(self, text):
        """Fix common encoding issues"""
        if not text:
            return text
            
        fixed_text = text
        for wrong, correct in self.encoding_fixes.items():
            if wrong in fixed_text:
                fixed_text = fixed_text.replace(wrong, correct)
                self.stats['fixed_encoding'] += 1
        
        return fixed_text
    
    def clean_contacts(self, contacts):
        """Clean and validate contacts"""
        cleaned_contacts = []
        
        for contact in contacts:
            contact_type = contact.get('type', '')
            contact_value = contact.get('value', '').strip()
            
            # Skip empty values
            if not contact_value:
                continue
            
            if contact_type == 'phone':
                # Check if it's actually a date
                if self.is_date(contact_value):
                    self.stats['removed_fake_phones'] += 1
                    continue
                
                # Check if it's a valid phone number
                if not self.is_valid_phone(contact_value):
                    self.stats['removed_fake_phones'] += 1
                    continue
                
                # Clean the phone number format
                cleaned_contacts.append({
                    'type': 'phone',
                    'value': contact_value
                })
                
            elif contact_type == 'email':
                # Validate email
                if self.is_valid_email(contact_value):
                    cleaned_contacts.append({
                        'type': 'email',
                        'value': contact_value.lower()  # Normalize to lowercase
                    })
                else:
                    self.stats['removed_fake_emails'] += 1
                    
            elif contact_type == 'office_hours':
                # Keep office hours but fix encoding
                cleaned_contacts.append({
                    'type': 'office_hours',
                    'value': self.fix_encoding(contact_value)
                })
        
        return cleaned_contacts
    
    def clean_dates_deadlines(self, dates):
        """Clean the dates_deadlines field"""
        cleaned_dates = []
        
        for date in dates:
            if not date:
                continue
                
            # Skip overly long entries (likely concatenated text)
            if len(date) > 100:
                # Try to extract just the date part
                date_match = re.search(r'\d{1,2}[./]\d{1,2}[./]\d{2,4}', date)
                if date_match:
                    cleaned_dates.append(date_match.group())
                    self.stats['cleaned_dates'] += 1
                continue
            
            # Fix encoding in dates
            cleaned_date = self.fix_encoding(date)
            
            # Remove entries that are clearly not dates
            if not any(char.isdigit() for char in cleaned_date):
                continue
                
            cleaned_dates.append(cleaned_date)
        
        return cleaned_dates
    
    def clean_page(self, page):
        """Clean a single page entry"""
        cleaned_page = page.copy()
        
        # Clean contacts
        if 'contacts' in cleaned_page:
            cleaned_page['contacts'] = self.clean_contacts(cleaned_page['contacts'])
        
        # Clean dates_deadlines
        if 'dates_deadlines' in cleaned_page:
            cleaned_page['dates_deadlines'] = self.clean_dates_deadlines(cleaned_page['dates_deadlines'])
        
        # Fix encoding in main content
        if 'main_content' in cleaned_page:
            cleaned_page['main_content'] = self.fix_encoding(cleaned_page['main_content'])
        
        # Fix encoding in title
        if 'title' in cleaned_page:
            cleaned_page['title'] = self.fix_encoding(cleaned_page['title'])
        
        # Update last_updated to show when cleaned
        cleaned_page['last_cleaned'] = datetime.now().isoformat()
        
        return cleaned_page
    
    def clean_file(self, filename):
        """Clean a single JSON file"""
        filepath = os.path.join(self.data_dir, filename)
        
        if not os.path.exists(filepath):
            print(f"⚠️  File not found: {filepath}")
            return False
        
        try:
            # Load the data
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Clean each page
            cleaned_data = []
            for page in data:
                cleaned_page = self.clean_page(page)
                cleaned_data.append(cleaned_page)
                self.stats['total_pages_processed'] += 1
            
            # Create backup of original file
            backup_path = filepath.replace('.json', '_backup.json')
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            # Save cleaned data
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(cleaned_data, f, ensure_ascii=False, indent=2)
            
            print(f"✅ Cleaned {filename} ({len(cleaned_data)} pages)")
            return True
            
        except Exception as e:
            print(f"❌ Error cleaning {filename}: {e}")
            return False
    
    def clean_all_files(self):
        """Clean all JSON files in the data directory"""
        files_to_clean = [
            'academic_affairs.json',
            'admissions.json',
            'career_services.json',
            'faq.json',
            'international.json',
            'regulations.json',
            'student_services.json',
            'study_programs.json'
        ]
        
        print("🧹 Starting HTW Data Cleaning Process")
        print("=" * 50)
        print(f"📁 Data directory: {self.data_dir}")
        print(f"📝 Files to clean: {len(files_to_clean)}")
        print("=" * 50)
        
        successful = 0
        failed = 0
        
        for filename in files_to_clean:
            if self.clean_file(filename):
                successful += 1
            else:
                failed += 1
        
        # Print summary
        print("\n" + "=" * 50)
        print("📊 CLEANING SUMMARY")
        print("=" * 50)
        print(f"✅ Files successfully cleaned: {successful}")
        print(f"❌ Files failed: {failed}")
        print(f"📄 Total pages processed: {self.stats['total_pages_processed']}")
        print(f"\n🔧 Fixes applied:")
        print(f"  - Removed fake phone numbers: {self.stats['removed_fake_phones']}")
        print(f"  - Removed invalid emails: {self.stats['removed_fake_emails']}")
        print(f"  - Fixed encoding issues: {self.stats['fixed_encoding']}")
        print(f"  - Cleaned malformed dates: {self.stats['cleaned_dates']}")
        print("\n💾 Original files backed up with '_backup.json' suffix")
    
    def restore_from_backup(self, filename):
        """Restore a file from its backup"""
        filepath = os.path.join(self.data_dir, filename)
        backup_path = filepath.replace('.json', '_backup.json')
        
        if not os.path.exists(backup_path):
            print(f"⚠️  No backup found for {filename}")
            return False
        
        try:
            with open(backup_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            print(f"✅ Restored {filename} from backup")
            return True
            
        except Exception as e:
            print(f"❌ Error restoring {filename}: {e}")
            return False
    
    def validate_cleaned_data(self):
        """Validate the cleaned data to ensure quality"""
        print("\n🔍 Validating Cleaned Data")
        print("=" * 50)
        
        files_to_check = [
            'academic_affairs.json',
            'admissions.json',
            'student_services.json'
        ]
        
        total_valid_phones = 0
        total_valid_emails = 0
        remaining_issues = 0
        
        for filename in files_to_check:
            filepath = os.path.join(self.data_dir, filename)
            
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                for page in data:
                    for contact in page.get('contacts', []):
                        if contact['type'] == 'phone':
                            if self.is_valid_phone(contact['value']):
                                total_valid_phones += 1
                            else:
                                remaining_issues += 1
                                print(f"⚠️  Still invalid phone: {contact['value']}")
                        elif contact['type'] == 'email':
                            if self.is_valid_email(contact['value']):
                                total_valid_emails += 1
                            else:
                                remaining_issues += 1
                                print(f"⚠️  Still invalid email: {contact['value']}")
                    
                    # Check for remaining encoding issues
                    content = page.get('main_content', '')
                    if 'â€™' in content or 'â€œ' in content or 'Ã¼' in content:
                        remaining_issues += 1
                        
            except Exception as e:
                print(f"❌ Error validating {filename}: {e}")
        
        print(f"\n✅ Valid phones remaining: {total_valid_phones}")
        print(f"✅ Valid emails remaining: {total_valid_emails}")
        print(f"⚠️  Remaining issues: {remaining_issues}")


# Usage
if __name__ == "__main__":
    # Initialize the cleaner
    cleaner = HTWDataCleaner('htw_student_data')
    
    # Clean all files
    cleaner.clean_all_files()
    
    # Validate the results
    cleaner.validate_cleaned_data()
    
    # If you need to restore from backup:
    # cleaner.restore_from_backup('academic_affairs.json')
    
    print("\n✨ Data cleaning complete!")
    print("Your files have been cleaned and backups created.")
    print("You can now use the cleaned data for your model training.")