'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { auth } from '@/lib/auth';
import { Loader2 } from 'lucide-react';

interface ProtectedRouteProps {
  children: React.ReactNode;
  allowedRoles?: Array<'superadmin' | 'country_admin' | 'organization_admin' | 'admin' | 'user'>;
  redirectTo?: string;
}

export function ProtectedRoute({ 
  children, 
  allowedRoles,
  redirectTo 
}: ProtectedRouteProps) {
  const router = useRouter();
  const [isChecking, setIsChecking] = useState(true);
  const [isAuthorized, setIsAuthorized] = useState(false);

  useEffect(() => {
    const checkAuth = () => {
      if (!auth.isAuthenticated()) {
        router.push('/login');
        return;
      }

      if (allowedRoles) {
        const userRole = auth.getUserRole();
        if (!userRole || !allowedRoles.includes(userRole)) {
          router.push(redirectTo || auth.getRedirectPath());
          return;
        }
      }

      setIsAuthorized(true);
      setIsChecking(false);
    };

    checkAuth();
  }, [router, allowedRoles, redirectTo]);

  if (isChecking) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin mx-auto mb-4" />
          <p className="text-muted-foreground">Checking authentication...</p>
        </div>
      </div>
    );
  }

  if (!isAuthorized) {
    return null;
  }

  return <>{children}</>;
}

