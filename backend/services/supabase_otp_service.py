"""
Supabase OTP Service
Uses Supabase Auth for sending OTPs via email
"""

import os
from supabase import create_client, Client
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class SupabaseOTPService:
    def __init__(self):
        self.supabase_url = os.getenv('SUPABASE_URL', '')
        self.supabase_key = os.getenv('SUPABASE_ANON_KEY', '')
        self.enabled = bool(self.supabase_url and self.supabase_key)
        
        if self.enabled:
            try:
                self.client: Client = create_client(self.supabase_url, self.supabase_key)
                logger.info("Supabase OTP service initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Supabase: {str(e)}")
                self.enabled = False
        else:
            logger.warning("Supabase OTP service not configured - SUPABASE_URL and SUPABASE_ANON_KEY required")
    
    def send_otp(self, email: str, purpose: str = 'login') -> tuple[bool, Optional[str]]:
        """
        Send OTP via Supabase Auth
        
        Args:
            email: Recipient email address
            purpose: Purpose of OTP ('login', 'registration', 'password_reset')
        
        Returns:
            Tuple of (success, otp_code)
            Note: Supabase handles OTP internally, so we return None for otp_code
        """
        if not self.enabled:
            logger.warning(f"Supabase OTP service disabled - OTP would be sent to {email}")
            return False, None
        
        try:
            # Supabase Auth sends OTP via email automatically
            # For sign-in, use sign_in_with_otp
            # For sign-up, use sign_up with email
            
            if purpose == 'login':
                # Send magic link/OTP for sign-in
                response = self.client.auth.sign_in_with_otp({
                    "email": email,
                    "options": {
                        "should_create_user": False  # Don't create user if doesn't exist
                    }
                })
            elif purpose == 'registration':
                # Sign up with OTP
                response = self.client.auth.sign_up({
                    "email": email,
                    "options": {
                        "email_redirect_to": None  # No redirect needed for OTP
                    }
                })
            elif purpose == 'password_reset':
                # Password reset OTP
                response = self.client.auth.reset_password_for_email(
                    email,
                    {"redirect_to": None}
                )
            else:
                logger.error(f"Unknown OTP purpose: {purpose}")
                return False, None
            
            logger.info(f"Supabase OTP sent to {email} for {purpose}")
            return True, None  # Supabase handles OTP internally
            
        except Exception as e:
            logger.error(f"Failed to send Supabase OTP to {email}: {str(e)}")
            return False, None
    
    def verify_otp(self, email: str, token: str, purpose: str = 'login') -> bool:
        """
        Verify OTP token from Supabase
        
        Args:
            email: User's email
            token: OTP token from email
            purpose: Purpose of OTP
        
        Returns:
            True if valid, False otherwise
        """
        if not self.enabled:
            return False
        
        try:
            # Supabase handles OTP verification through session
            # The token is typically used in a callback URL
            # For our use case, we'll need to verify the session
            
            # Note: Supabase OTP flow is different - it uses magic links
            # We may need to adapt our flow or use Supabase's session-based auth
            
            # For now, return False - this needs to be adapted based on Supabase's actual OTP flow
            logger.warning("Supabase OTP verification needs to be adapted to Supabase's flow")
            return False
            
        except Exception as e:
            logger.error(f"Failed to verify Supabase OTP: {str(e)}")
            return False

# Global Supabase OTP service instance
supabase_otp_service = SupabaseOTPService()

