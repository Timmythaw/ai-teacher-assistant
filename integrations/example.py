#!/usr/bin/env python3
"""
Fetch Myanmar Children Growth Survey Form
Targeted script for form ID: 10LPvykuD6mH2S2FfGQigXDqo6z9oAdYjYcFRldotz3o
"""

import os
import json
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

def fetch_myanmar_survey():
    """Fetch the specific Myanmar children growth survey form"""
    
    # Form ID from the URL
    FORM_ID = "10LPvykuD6mH2S2FfGQigXDqo6z9oAdYjYcFRldotz3o"
    
    print("🔍 Fetching Myanmar Children Growth Survey Form...")
    print(f"📋 Form ID: {FORM_ID}")
    print("=" * 60)
    
    try:
        # Check if token exists
        if not os.path.exists("token.json"):
            print("❌ No token.json found. Please run auth_google.py first.")
            return
        
        # Load credentials with Forms API scopes
        SCOPES = [
            'https://www.googleapis.com/auth/forms',
            'https://www.googleapis.com/auth/forms.responses.readonly'
        ]
        
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
        
        if not creds.valid:
            if creds.expired and creds.refresh_token:
                print("🔄 Refreshing expired token...")
                creds.refresh(Request())
            else:
                print("❌ Invalid credentials. Please re-authenticate.")
                return
        
        print("✅ Credentials loaded successfully!")
        
        # Build Forms service
        forms_service = build('forms', 'v1', credentials=creds)
        print("✅ Forms service built successfully!")
        
        # Fetch form details
        print("\n📋 Fetching form details...")
        try:
            form = forms_service.forms().get(formId=FORM_ID).execute()
            
            # Display form information
            info = form.get('info', {})
            print(f"✅ Form Title: {info.get('title', 'Untitled')}")
            print(f"   Description: {info.get('description', 'No description')}")
            print(f"   Document Title: {info.get('documentTitle', 'No document title')}")
            
            # Display questions
            print(f"\n📝 Form Questions ({len(form.get('items', []))} questions):")
            for i, item in enumerate(form.get('items', []), 1):
                title = item.get('title', 'Untitled Question')
                question_type = "Unknown"
                
                if 'questionItem' in item:
                    question = item['questionItem'].get('question', {})
                    if 'textQuestion' in question:
                        question_type = "Short Answer"
                    elif 'choiceQuestion' in question:
                        question_type = "Multiple Choice"
                    elif 'paragraphQuestion' in question:
                        question_type = "Paragraph"
                
                print(f"   {i}. {title} ({question_type})")
            
            # Save form structure to file
            with open(f"myanmar_survey_form_structure.json", "w", encoding="utf-8") as f:
                json.dump(form, f, indent=2, ensure_ascii=False)
            print(f"\n💾 Form structure saved to: myanmar_survey_form_structure.json")
            
        except Exception as e:
            print(f"❌ Error fetching form details: {e}")
            return
        
        # Fetch form responses
        print("\n📊 Fetching form responses...")
        try:
            responses = forms_service.forms().responses().list(formId=FORM_ID).execute()
            
            response_list = responses.get('responses', [])
            print(f"✅ Found {len(response_list)} responses")
            
            if response_list:
                print(f"\n📈 Response Summary:")
                print(f"   Total responses: {len(response_list)}")
                
                # Show first few responses
                for i, response in enumerate(response_list[:3], 1):
                    print(f"\n   Response {i}:")
                    print(f"     Submitted: {response.get('lastSubmittedTime', 'Unknown')}")
                    
                    # Show answers
                    answers = response.get('answers', {})
                    for question_id, answer in answers.items():
                        if 'textAnswers' in answer:
                            value = answer['textAnswers']['answers'][0]['value']
                            print(f"       Answer: {value}")
                        elif 'choiceAnswers' in answer:
                            value = answer['choiceAnswers']['answers'][0]['value']
                            print(f"       Choice: {value}")
                
                # Save responses to file
                with open(f"myanmar_survey_responses.json", "w", encoding="utf-8") as f:
                    json.dump(responses, f, indent=2, ensure_ascii=False)
                print(f"\n💾 Responses saved to: myanmar_survey_responses.json")
                
                # Export to CSV
                export_to_csv(form, response_list)
                
            else:
                print("📝 No responses found yet")
                
        except Exception as e:
            print(f"❌ Error fetching responses: {e}")
            print("💡 This might be due to network issues or API permissions")
        
    except Exception as e:
        print(f"❌ General error: {e}")

def export_to_csv(form, responses):
    """Export responses to CSV format"""
    try:
        import csv
        
        # Get question titles
        questions = []
        for item in form.get('items', []):
            if 'title' in item:
                questions.append(item['title'])
        
        # Create CSV
        csv_filename = "myanmar_survey_responses.csv"
        with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # Write header
            header = ['Timestamp'] + questions
            writer.writerow(header)
            
            # Write responses
            for response in responses:
                row = [response.get('lastSubmittedTime', '')]
                
                # Get answers for each question
                answers = response.get('answers', {})
                for item in form.get('items', []):
                    item_id = item.get('itemId')
                    if item_id in answers:
                        answer = answers[item_id]
                        if 'textAnswers' in answer:
                            value = answer['textAnswers']['answers'][0]['value']
                        elif 'choiceAnswers' in answer:
                            value = answer['choiceAnswers']['answers'][0]['value']
                        else:
                            value = ''
                        row.append(value)
                    else:
                        row.append('')
                
                writer.writerow(row)
        
        print(f"💾 CSV export saved to: {csv_filename}")
        
    except Exception as e:
        print(f"❌ Error exporting to CSV: {e}")

if __name__ == "__main__":
    fetch_myanmar_survey()