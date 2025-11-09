"""
Email Service for Sending OTPs and Notifications
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        self.smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.smtp_user = os.getenv('SMTP_USER', '')
        self.smtp_password = os.getenv('SMTP_PASSWORD', '')
        self.from_email = os.getenv('FROM_EMAIL', self.smtp_user)
        self.enabled = bool(self.smtp_user and self.smtp_password)
        
        if not self.enabled:
            logger.warning("Email service not configured - SMTP credentials missing")
    
    def send_otp(self, to_email: str, otp_code: str, purpose: str = 'login') -> bool:
        """
        Send OTP code via email
        
        Args:
            to_email: Recipient email address
            otp_code: OTP code to send
            purpose: Purpose of OTP ('login', 'registration', 'password_reset')
        
        Returns:
            True if email sent successfully, False otherwise
        """
        if not self.enabled:
            logger.warning(f"Email service disabled - OTP {otp_code} would be sent to {to_email}")
            # In development, log the OTP instead
            logger.info(f"OTP for {to_email}: {otp_code}")
            return True  # Return True for development
        
        try:
            subject_map = {
                'login': 'Your Login OTP - Ration Smart Feed Library',
                'registration': 'Your Registration OTP - Ration Smart Feed Library',
                'password_reset': 'Password Reset OTP - Ration Smart Feed Library'
            }
            
            subject = subject_map.get(purpose, 'Your OTP - Ration Smart Feed Library')
            
            body = f"""
            <html>
            <body>
                <h2>Your OTP Code</h2>
                <p>Your OTP code is: <strong style="font-size: 24px; letter-spacing: 4px;">{otp_code}</strong></p>
                <p>This code will expire in 10 minutes.</p>
                <p>If you didn't request this code, please ignore this email.</p>
                <hr>
                <p style="color: #666; font-size: 12px;">Ration Smart Feed Library</p>
            </body>
            </html>
            """
            
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.from_email
            msg['To'] = to_email
            
            msg.attach(MIMEText(body, 'html'))
            
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            
            logger.info(f"OTP email sent to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send OTP email to {to_email}: {str(e)}")
            return False
    
    def send_welcome_email(self, to_email: str, name: str) -> bool:
        """Send welcome email to new user"""
        if not self.enabled:
            logger.info(f"Welcome email would be sent to {to_email}")
            return True
        
        try:
            subject = 'Welcome to Ration Smart Feed Library'
            body = f"""
            <html>
            <body>
                <h2>Welcome, {name}!</h2>
                <p>Thank you for registering with Ration Smart Feed Library.</p>
                <p>You can now access the feed database and start managing your feeds.</p>
                <hr>
                <p style="color: #666; font-size: 12px;">Ration Smart Feed Library</p>
            </body>
            </html>
            """
            
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.from_email
            msg['To'] = to_email
            msg.attach(MIMEText(body, 'html'))
            
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            
            return True
        except Exception as e:
            logger.error(f"Failed to send welcome email: {str(e)}")
            return False

# Global email service instance
email_service = EmailService()

