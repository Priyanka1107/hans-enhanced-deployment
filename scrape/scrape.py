import requests
from bs4 import BeautifulSoup
import json
import time
from urllib.parse import urljoin, urlparse
import re
from datetime import datetime
import hashlib

class HTWStudentInfoScraper:
    """
    Specialized scraper for HTW Berlin website focusing on student-relevant information
    """
    
    def __init__(self):
        self.base_url = "https://www.htw-berlin.de/en/"
        self.visited_urls = set()
        self.scraped_data = {
            'admissions': [],
            'study_programs': [],
            'student_services': [],
            'academic_affairs': [],
            'campus_life': [],
            'international': [],
            'career_services': [],
            'facilities': [],
            'regulations': [],
            'faq': [],
            'contact_info': [],
            'news_events': []
        }
        
        # Priority URLs for student information
        self.priority_paths = [
            '/en/studies/',
            '/en/study/degree-programmes/',
            '/en/study/application-enrollment/',
            '/en/study/student-services/',
            '/en/study/counselling/',
            '/en/study/academic-affairs/',
            '/en/study/examination-office/',
            '/en/international/',
            '/en/campus-life/',
            '/en/career-service/',
            '/en/study/financing/',
            '/en/study/academic-calendar/',
            '/en/study/exchange/',
            '/en/facilities/',
            '/en/library/',
            '/en/it-services/',
            '/en/mensa/',  # Cafeteria
            '/en/housing/',
            '/en/health/',
            '/en/sports/'
        ]
        
        # Keywords that indicate student-relevant content
        self.student_keywords = [
            'student', 'study', 'course', 'semester', 'exam', 'enrollment',
            'admission', 'bachelor', 'master', 'degree', 'programme', 'module',
            'credit', 'ects', 'registration', 'deadline', 'schedule', 'timetable',
            'tuition', 'fee', 'scholarship', 'grant', 'housing', 'dormitory',
            'campus', 'library', 'mensa', 'cafeteria', 'counselling', 'advising',
            'international', 'exchange', 'erasmus', 'visa', 'orientation',
            'graduation', 'thesis', 'internship', 'career', 'job', 'certificate'
        ]
    
    def calculate_relevance_score(self, text, url):
        """Calculate how relevant content is for students"""
        score = 0
        text_lower = text.lower()
        url_lower = url.lower()
        
        # Check URL relevance
        for path in self.priority_paths:
            if path in url_lower:
                score += 10
                break
        
        # Check keyword density
        for keyword in self.student_keywords:
            score += text_lower.count(keyword) * 2
        
        # Boost score for certain critical pages
        if any(term in url_lower for term in ['faq', 'contact', 'emergency', 'help']):
            score += 15
        
        return score
    
    def categorize_content(self, url, text):
        """Determine which category the content belongs to"""
        url_lower = url.lower()
        text_lower = text.lower()
        
        if 'admission' in url_lower or 'application' in url_lower or 'enrollment' in url_lower:
            return 'admissions'
        elif 'programme' in url_lower or 'course' in url_lower or 'curriculum' in url_lower:
            return 'study_programs'
        elif 'student-service' in url_lower or 'counselling' in url_lower:
            return 'student_services'
        elif 'exam' in url_lower or 'academic' in url_lower or 'regulation' in url_lower:
            return 'academic_affairs'
        elif 'campus' in url_lower or 'mensa' in url_lower or 'sport' in url_lower:
            return 'campus_life'
        elif 'international' in url_lower or 'exchange' in url_lower or 'visa' in url_lower:
            return 'international'
        elif 'career' in url_lower or 'job' in url_lower or 'internship' in url_lower:
            return 'career_services'
        elif 'library' in url_lower or 'it-service' in url_lower or 'facility' in url_lower:
            return 'facilities'
        elif 'regulation' in text_lower or 'policy' in text_lower:
            return 'regulations'
        elif 'faq' in url_lower or 'frequently asked' in text_lower:
            return 'faq'
        elif 'contact' in url_lower or 'office hour' in text_lower:
            return 'contact_info'
        elif 'news' in url_lower or 'event' in url_lower:
            return 'news_events'
        else:
            return 'student_services'  # Default category
    
    def extract_structured_info(self, soup, url):
        """Extract specific structured information useful for student queries"""
        info = {
            'url': url,
            'title': '',
            'main_content': '',
            'contacts': [],
            'dates_deadlines': [],
            'requirements': [],
            'procedures': [],
            'links': [],
            'faqs': [],
            'relevance_score': 0,
            'last_updated': datetime.now().isoformat(),
            'content_hash': ''
        }
        
        # Extract title
        title = soup.find('title')
        if title:
            info['title'] = title.text.strip()
        
        # Extract main content
        main_content = self.extract_main_content(soup)
        info['main_content'] = main_content
        
        # Calculate relevance score
        info['relevance_score'] = self.calculate_relevance_score(main_content, url)
        
        # Generate content hash for deduplication
        info['content_hash'] = hashlib.md5(main_content.encode()).hexdigest()
        
        # Extract contact information
        info['contacts'] = self.extract_contacts(soup)
        
        # Extract dates and deadlines
        info['dates_deadlines'] = self.extract_dates(soup)
        
        # Extract requirements (look for lists near requirement keywords)
        info['requirements'] = self.extract_requirements(soup)
        
        # Extract step-by-step procedures
        info['procedures'] = self.extract_procedures(soup)
        
        # Extract FAQs if present
        info['faqs'] = self.extract_faqs(soup)
        
        # Extract useful links
        info['links'] = self.extract_useful_links(soup, url)
        
        return info
    
    def extract_main_content(self, soup):
        """Extract and clean main text content"""
        # Remove script and style elements
        for element in soup(['script', 'style', 'nav', 'footer', 'header']):
            element.decompose()
        
        # Look for main content areas
        main_content = soup.find('main') or soup.find('div', class_='content') or soup.body
        
        if main_content:
            # Get text with proper spacing
            text = main_content.get_text(separator=' ', strip=True)
            # Clean up excessive whitespace
            text = re.sub(r'\s+', ' ', text)
            return text
        
        return ""
    
    def extract_contacts(self, soup):
        """Extract email addresses, phone numbers, and office locations"""
        contacts = []
        text = soup.get_text()
        
        # Find email addresses
        emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
        
        # Find phone numbers (German format)
        phones = re.findall(r'[\+49\s]*[(]?[0-9]{2,4}[)]?[-.\s]?[0-9]{2,4}[-.\s]?[0-9]{2,4}[-.\s]?[0-9]{0,4}', text)
        
        # Look for office hours
        office_hours = re.findall(r'(?:Monday|Tuesday|Wednesday|Thursday|Friday|Mon|Tue|Wed|Thu|Fri).*?[0-9]{1,2}:[0-9]{2}.*?[0-9]{1,2}:[0-9]{2}', text, re.IGNORECASE)
        
        for email in emails[:5]:  # Limit to avoid spam
            contacts.append({'type': 'email', 'value': email})
        
        for phone in phones[:3]:
            contacts.append({'type': 'phone', 'value': phone.strip()})
            
        for hours in office_hours[:2]:
            contacts.append({'type': 'office_hours', 'value': hours})
        
        return contacts
    
    def extract_dates(self, soup):
        """Extract important dates and deadlines"""
        dates = []
        text = soup.get_text()
        
        # Common date patterns
        date_patterns = [
            r'\b\d{1,2}[./]\d{1,2}[./]\d{2,4}\b',  # DD.MM.YYYY or DD/MM/YYYY
            r'\b\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{2,4}\b',
            r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{2,4}\b'
        ]
        
        for pattern in date_patterns:
            found_dates = re.findall(pattern, text, re.IGNORECASE)
            dates.extend(found_dates[:5])  # Limit number of dates
        
        # Look for deadline keywords near dates
        deadline_contexts = re.findall(
            r'(?:deadline|due date|submission|application period|registration).*?(?:\d{1,2}[./]\d{1,2}[./]\d{2,4}|\w+\s+\d{1,2},?\s+\d{4})',
            text, re.IGNORECASE
        )
        
        return list(set(dates + deadline_contexts))[:10]
    
    def extract_requirements(self, soup):
        """Extract requirement lists"""
        requirements = []
        
        # Look for requirement sections
        req_headers = soup.find_all(['h2', 'h3', 'h4'], 
                                   string=re.compile(r'requirement|prerequisite|eligibility|qualification', re.IGNORECASE))
        
        for header in req_headers:
            next_element = header.find_next_sibling()
            if next_element and next_element.name in ['ul', 'ol']:
                items = next_element.find_all('li')
                requirements.extend([item.get_text(strip=True) for item in items[:10]])
        
        return requirements
    
    def extract_procedures(self, soup):
        """Extract step-by-step procedures"""
        procedures = []
        
        # Look for ordered lists that might be procedures
        proc_headers = soup.find_all(['h2', 'h3', 'h4'],
                                    string=re.compile(r'how to|steps|procedure|process|guide', re.IGNORECASE))
        
        for header in proc_headers:
            next_element = header.find_next_sibling()
            if next_element and next_element.name == 'ol':
                steps = next_element.find_all('li')
                procedure = {
                    'title': header.get_text(strip=True),
                    'steps': [step.get_text(strip=True) for step in steps[:15]]
                }
                procedures.append(procedure)
        
        return procedures
    
    def extract_faqs(self, soup):
        """Extract FAQ sections"""
        faqs = []
        
        # Look for FAQ patterns
        faq_section = soup.find_all(string=re.compile(r'frequently asked questions|faq', re.IGNORECASE))
        
        for section in faq_section:
            parent = section.find_parent()
            if parent:
                # Look for Q&A patterns
                questions = parent.find_all(['h3', 'h4', 'strong', 'b'])
                for q in questions[:10]:
                    answer = q.find_next_sibling()
                    if answer:
                        faqs.append({
                            'question': q.get_text(strip=True),
                            'answer': answer.get_text(strip=True)[:500]  # Limit answer length
                        })
        
        return faqs
    
    def extract_useful_links(self, soup, current_url):
        """Extract links that are useful for students"""
        links = []
        
        # Find all links
        for link in soup.find_all('a', href=True):
            href = link['href']
            text = link.get_text(strip=True)
            
            # Check if link text contains student keywords
            if any(keyword in text.lower() for keyword in self.student_keywords[:20]):
                absolute_url = urljoin(current_url, href)
                if self.is_valid_url(absolute_url):
                    links.append({
                        'url': absolute_url,
                        'text': text[:100]
                    })
        
        return links[:20]  # Limit number of links
    
    def is_valid_url(self, url):
        """Check if URL is valid and English"""
        parsed = urlparse(url)
        return (
            parsed.netloc in ["www.htw-berlin.de", "htw-berlin.de"] and
            "/en/" in url and
            not url.endswith(('.pdf', '.jpg', '.png', '.doc', '.docx'))  # Skip documents for now
        )
    
    def scrape_page(self, url):
        """Scrape a single page with student focus"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Educational Bot for Student Services)'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract structured information
            page_info = self.extract_structured_info(soup, url)
            
            # Only save if relevance score is above threshold
            if page_info['relevance_score'] > 5:
                category = self.categorize_content(url, page_info['main_content'])
                self.scraped_data[category].append(page_info)
                print(f"✓ Scraped: {url} (Relevance: {page_info['relevance_score']}, Category: {category})")
            else:
                print(f"⊘ Skipped: {url} (Low relevance: {page_info['relevance_score']})")
            
            return page_info
            
        except Exception as e:
            print(f"✗ Error scraping {url}: {e}")
            return None
    
    def crawl_smart(self, max_pages=100):
        """Smart crawling that prioritizes student-relevant pages"""
        # Start with priority URLs
        to_visit = []
        
        # Add priority paths
        for path in self.priority_paths:
            full_url = urljoin(self.base_url, path)
            to_visit.append((full_url, 100))  # High priority score
        
        # Add base URL
        to_visit.append((self.base_url, 50))
        
        pages_scraped = 0
        
        while to_visit and pages_scraped < max_pages:
            # Sort by priority (higher score first)
            to_visit.sort(key=lambda x: x[1], reverse=True)
            url, priority = to_visit.pop(0)
            
            if url in self.visited_urls:
                continue
            
            self.visited_urls.add(url)
            page_info = self.scrape_page(url)
            
            if page_info:
                pages_scraped += 1
                
                # Add new links with calculated priority
                for link_info in page_info['links']:
                    link_url = link_info['url']
                    if link_url not in self.visited_urls:
                        # Calculate priority based on URL and text
                        link_priority = self.calculate_relevance_score(link_info['text'], link_url)
                        to_visit.append((link_url, link_priority))
            
            # Rate limiting
            time.sleep(1)
        
        return self.scraped_data
    
    def save_data(self, output_dir='htw_student_data'):
        """Save scraped data in organized format"""
        import os
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Save each category separately
        for category, data in self.scraped_data.items():
            if data:  # Only save non-empty categories
                filename = os.path.join(output_dir, f'{category}.json')
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                print(f"Saved {len(data)} items to {filename}")
        
        # Save summary
        summary = {
            'total_pages': sum(len(data) for data in self.scraped_data.values()),
            'categories': {cat: len(data) for cat, data in self.scraped_data.items()},
            'scrape_date': datetime.now().isoformat()
        }
        
        with open(os.path.join(output_dir, 'summary.json'), 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"\n📊 Scraping Summary:")
        print(f"Total pages scraped: {summary['total_pages']}")
        for cat, count in summary['categories'].items():
            if count > 0:
                print(f"  - {cat}: {count} pages")
    
    def generate_training_data(self, output_file='training_data.jsonl'):
        """Generate training data in a format suitable for fine-tuning"""
        training_examples = []
        
        for category, pages in self.scraped_data.items():
            for page in pages:
                # Skip low-relevance content
                if page['relevance_score'] < 10:
                    continue
                
                # Create Q&A pairs from FAQs
                for faq in page['faqs']:
                    training_examples.append({
                        'prompt': faq['question'],
                        'completion': faq['answer'],
                        'category': category,
                        'source_url': page['url']
                    })
                
                # Create informational responses
                if page['main_content']:
                    # Generate a summary prompt
                    training_examples.append({
                        'prompt': f"Tell me about {page['title']}",
                        'completion': page['main_content'][:1000],  # Limit length
                        'category': category,
                        'source_url': page['url']
                    })
                
                # Create procedure-based responses
                for procedure in page['procedures']:
                    training_examples.append({
                        'prompt': f"How do I {procedure['title'].lower()}?",
                        'completion': "Here are the steps:\n" + "\n".join(f"{i+1}. {step}" for i, step in enumerate(procedure['steps'])),
                        'category': category,
                        'source_url': page['url']
                    })
        
        # Save as JSONL for training
        with open(output_file, 'w', encoding='utf-8') as f:
            for example in training_examples:
                f.write(json.dumps(example, ensure_ascii=False) + '\n')
        
        print(f"\n🎓 Generated {len(training_examples)} training examples")
        return training_examples


# Example usage
if __name__ == "__main__":
    print("🕷️ Starting HTW Student Information Scraper...")
    print("=" * 50)
    
    scraper = HTWStudentInfoScraper()
    
    # Perform smart crawling
    print("\n📚 Crawling student-relevant pages...")
    data = scraper.crawl_smart(max_pages=100)
    
    # Save organized data
    print("\n💾 Saving data...")
    scraper.save_data()
    
    # Generate training data for your model
    print("\n🤖 Generating training data...")
    scraper.generate_training_data()
    
    print("\n✅ Scraping complete!")
    print("\nYou can now use the data in 'htw_student_data/' folder to train your model.")
    print("The 'training_data.jsonl' file contains Q&A pairs ready for fine-tuning.")