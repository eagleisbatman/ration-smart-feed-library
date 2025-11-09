'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import React from 'react';
import { useTranslations } from '@/hooks/use-translations';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useMutation } from '@tanstack/react-query';
import { authApi } from '@/lib/api';
import { auth } from '@/lib/auth';
import { toast } from 'sonner';
import { Loader2, Mail, Shield } from 'lucide-react';

export default function LoginPage() {
  const t = useTranslations('auth');
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [otpCode, setOtpCode] = useState('');
  const [step, setStep] = useState<'email' | 'otp'>('email');

  // Request OTP mutation
  const requestOtpMutation = useMutation({
    mutationFn: async (email: string) => {
      const response = await authApi.requestOtp(email, 'login');
      return response.data;
    },
    onSuccess: (data) => {
      toast.success('OTP sent to your email');
      setStep('otp');
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to send OTP');
    },
  });

  // Login mutation
  const loginMutation = useMutation({
    mutationFn: async ({ email, otpCode }: { email: string; otpCode: string }) => {
      const response = await authApi.loginWithOtp(email, otpCode);
      return response.data;
    },
    onSuccess: (data) => {
      const user = data.user;
      
      // Store user info using auth utility
      auth.setCurrentUser(user);
      
      // Determine role and redirect
      const redirectPath = auth.getRedirectPath();
      router.push(redirectPath);
      
      toast.success('Login successful');
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Invalid OTP code');
    },
  });

  const handleRequestOtp = (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) {
      toast.error('Please enter your email');
      return;
    }
    requestOtpMutation.mutate(email);
  };

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    if (!otpCode || otpCode.length !== 6) {
      toast.error('Please enter a valid 6-digit OTP code');
      return;
    }
    loginMutation.mutate({ email, otpCode });
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-background to-muted p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="space-y-1">
          <div className="flex items-center justify-center mb-4">
            <Shield className="h-12 w-12 text-primary" />
          </div>
          <CardTitle className="text-2xl text-center">Login</CardTitle>
          <CardDescription className="text-center">
            {step === 'email' 
              ? 'Enter your email to receive an OTP code'
              : 'Enter the 6-digit OTP code sent to your email'
            }
          </CardDescription>
        </CardHeader>
        <CardContent>
          {step === 'email' ? (
            <form onSubmit={handleRequestOtp} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <div className="relative">
                  <Mail className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                  <Input
                    id="email"
                    type="email"
                    placeholder="your.email@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="pl-10"
                    required
                    disabled={requestOtpMutation.isPending}
                  />
                </div>
              </div>
              <Button 
                type="submit" 
                className="w-full" 
                disabled={requestOtpMutation.isPending}
              >
                {requestOtpMutation.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Sending OTP...
                  </>
                ) : (
                  'Send OTP'
                )}
              </Button>
            </form>
          ) : (
            <form onSubmit={handleLogin} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="email-display">Email</Label>
                <Input
                  id="email-display"
                  type="email"
                  value={email}
                  disabled
                  className="bg-muted"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="otp">OTP Code</Label>
                <Input
                  id="otp"
                  type="text"
                  placeholder="000000"
                  value={otpCode}
                  onChange={(e) => {
                    const value = e.target.value.replace(/\D/g, '').slice(0, 6);
                    setOtpCode(value);
                  }}
                  maxLength={6}
                  className="text-center text-2xl tracking-widest"
                  required
                  disabled={loginMutation.isPending}
                />
                <p className="text-xs text-muted-foreground text-center">
                  Enter the 6-digit code sent to your email
                </p>
              </div>
              <div className="flex gap-2">
                <Button
                  type="button"
                  variant="outline"
                  className="flex-1"
                  onClick={() => {
                    setStep('email');
                    setOtpCode('');
                  }}
                  disabled={loginMutation.isPending}
                >
                  Back
                </Button>
                <Button 
                  type="submit" 
                  className="flex-1"
                  disabled={loginMutation.isPending || otpCode.length !== 6}
                >
                  {loginMutation.isPending ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Logging in...
                    </>
                  ) : (
                    'Login'
                  )}
                </Button>
              </div>
              <Button
                type="button"
                variant="ghost"
                className="w-full text-sm"
                onClick={() => {
                  requestOtpMutation.mutate(email);
                  setOtpCode('');
                }}
                disabled={requestOtpMutation.isPending}
              >
                Resend OTP
              </Button>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

