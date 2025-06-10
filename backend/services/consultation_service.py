# -*- coding: utf-8 -*-
"""AI Disease Consultation Service"""

import os
import requests
import logging
from dotenv import load_dotenv

class DiseaseConsultation:
    """
    AI-powered medical consultation service using OpenRouter
    """
    
    def __init__(self):
        """
        Initialize the consultation service
        """
        load_dotenv()
        
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable is not set")
        print("Loaded API Key:", self.api_key)

            
        self.base_url = "https://openrouter.ai/api/v1" 
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        self.timeout = 30  # Timeout in seconds
    
    def get_disease_analysis(self, disease_name):
        """
        Get AI analysis for a specific disease
        
        :param disease_name: Name of the disease to analyze
        :return: Consultation text or None if failed
        """
        if not disease_name or not isinstance(disease_name, str):
            logging.error("Invalid disease name provided")
            return None

        try:
            payload = {
                "model": "deepseek/deepseek-r1:free",
                "messages": [
                    {
                        "role": "system",
                        "content": self._get_system_prompt()
                    },
                    {
                        "role": "user",
                        "content": f"What is {disease_name}?"
                    }
                ]
            }
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=self.timeout
            )
            
            response.raise_for_status()
            
            response_data = response.json()
            if not response_data.get('choices'):
                logging.error("No choices in API response")
                return None
                
            return response_data['choices'][0]['message']['content']
            
        except requests.exceptions.RequestException as e:
            logging.error(f"API request failed: {str(e)}")
            return None
        except Exception as e:
            logging.error(f"Unexpected error: {str(e)}")
            return None
    
    # In services/consultation_service.py - Replace _get_system_prompt content
    def _get_system_prompt(self):
        """
        Get the system prompt for the AI consultation (Simplified: Heading + Content Below)
        """
        return (
        "You are a medical AI expert providing structured and scientifically accurate disease analyses. "
        "Your response MUST follow the structure below EXACTLY. Use plain text numbering (1., 2., 3., etc.) for the main sections only. "
        "Do not use any markdown formatting (like ##, *, -) or bullet points. Write the information for each section in natural sentences or simple paragraphs.\n\n" # Removed bullet point instruction
    
        "**CRITICAL INSTRUCTION:** For each numbered heading (e.g., '1. Disease Name:'), the corresponding information MUST begin on the *next* line, directly below the heading. **DO NOT** place any information on the same line as the numbered heading itself.\n\n"
    
        "Follow this specific structure:\n\n"
    
        "1. Disease Name:\n" # Heading on its own line
        "[State the disease name clearly.]\n\n" # Content placeholder below
    
        "2. Definition:\n" # Heading on its own line
        "[Provide the definition.]\n\n" # Content placeholder below
    
        "3. Key Symptoms & Signs:\n" # Heading on its own line
        "[Describe the common symptoms, severe symptoms/when to seek urgent care, and if asymptomatic presentation is possible.]\n\n" # Combine description
    
        "4. Causes & Risk Factors:\n" # Heading on its own line
        "[Describe the main causes, key risk factors, and contributing lifestyle/environmental factors. State 'Not Applicable' for causes if relevant.]\n\n" # Combine description
    
        "5. Transmission (if applicable):\n" # Heading on its own line
        "[Describe how it spreads or state 'Not Transmissible'. Mention other routes if relevant or state 'None'.]\n\n" # Combine description
    
        "6. Treatment & Management:\n" # Heading on its own line
        "[Describe the general approach, how mild cases are managed, common medical treatments for moderate/severe cases, and the vaccination status ('Not Applicable' if none).]\n\n" # Combine description
    
        "7. Prevention & Precautions:\n" # Heading on its own line
        "[Describe key preventive measures and actions to take if exposed or diagnosed.]\n\n" # Combine description
    
        "8. Potential Complications & Follow-Up:\n" # Heading on its own line
        "[Describe possible long-term effects/complications and recommended follow-up monitoring.]\n\n" # Combine description
    
        "**REMINDER:** Ensure all information starts on the line *immediately following* its numbered heading. Maintain scientific accuracy and use clear language suitable for a general audience."
        )