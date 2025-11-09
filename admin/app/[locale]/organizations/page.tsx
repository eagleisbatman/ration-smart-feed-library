'use client';

import { useState } from 'react';
import { DashboardLayout } from '@/components/layout/dashboard-layout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { organizationsApi, auth } from '@/lib/api';
import { toast } from 'sonner';
import { Plus, Key, Copy, Trash2, Eye, EyeOff, Building2, Loader2, Mail } from 'lucide-react';
import { ProtectedRoute } from '@/components/auth/protected-route';

function OrganizationsContent() {
  const queryClient = useQueryClient();
  const user = auth.getCurrentUser();
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [isLoginDialogOpen, setIsLoginDialogOpen] = useState(false);
  const [isRegisterDialogOpen, setIsRegisterDialogOpen] = useState(false);
  const [selectedOrgId, setSelectedOrgId] = useState<string | null>(null);
  const [visibleApiKeys, setVisibleApiKeys] = useState<Set<string>>(new Set());
  const [activeTab, setActiveTab] = useState<'admin' | 'self-service'>('admin');

  // Registration form state
  const [regEmail, setRegEmail] = useState('');
  const [regOtpCode, setRegOtpCode] = useState('');
  const [regStep, setRegStep] = useState<'email' | 'otp'>('email');
  const [regName, setRegName] = useState('');
  const [regSlug, setRegSlug] = useState('');

  // Login form state
  const [loginEmail, setLoginEmail] = useState('');
  const [loginOtpCode, setLoginOtpCode] = useState('');
  const [loginStep, setLoginStep] = useState<'email' | 'otp'>('email');
  const [loggedInOrg, setLoggedInOrg] = useState<any>(null);

  // API Key creation state
  const [isCreateApiKeyDialogOpen, setIsCreateApiKeyDialogOpen] = useState(false);
  const [apiKeyOtpEmail, setApiKeyOtpEmail] = useState('');
  const [apiKeyOtpCode, setApiKeyOtpCode] = useState('');
  const [apiKeyStep, setApiKeyStep] = useState<'email' | 'otp'>('email');
  const [apiKeyName, setApiKeyName] = useState('');
  const [newApiKey, setNewApiKey] = useState<string | null>(null);

  // Fetch organizations (for admin view)
  const { data: organizations = [], isLoading: isLoadingOrgs } = useQuery({
    queryKey: ['organizations', user?.id],
    queryFn: () => {
      if (!user?.id) throw new Error('User not authenticated');
      return organizationsApi.getAll(user.id).then(res => res.data);
    },
    enabled: !!user?.id && activeTab === 'admin',
  });

  // Request OTP for registration
  const requestRegOtpMutation = useMutation({
    mutationFn: (email: string) => organizationsApi.requestOtp(email, 'registration'),
    onSuccess: () => {
      toast.success('OTP sent to your email');
      setRegStep('otp');
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to send OTP');
    },
  });

  // Register organization
  const registerMutation = useMutation({
    mutationFn: (data: any) => organizationsApi.register(data),
    onSuccess: (data) => {
      toast.success('Organization registered successfully');
      setIsRegisterDialogOpen(false);
      setRegEmail('');
      setRegOtpCode('');
      setRegName('');
      setRegSlug('');
      setRegStep('email');
      queryClient.invalidateQueries({ queryKey: ['organizations'] });
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Registration failed');
    },
  });

  // Request OTP for login
  const requestLoginOtpMutation = useMutation({
    mutationFn: (email: string) => organizationsApi.requestOtp(email, 'login'),
    onSuccess: () => {
      toast.success('OTP sent to your email');
      setLoginStep('otp');
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to send OTP');
    },
  });

  // Login organization
  const loginMutation = useMutation({
    mutationFn: (data: any) => organizationsApi.login(data),
    onSuccess: (data) => {
      toast.success('Login successful');
      setLoggedInOrg({
        ...data.data.organization,
        api_keys: data.data.api_keys || [],
      });
      setIsLoginDialogOpen(false);
      setLoginEmail('');
      setLoginOtpCode('');
      setLoginStep('email');
      setActiveTab('self-service');
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Login failed');
    },
  });

  // Request OTP for API key creation
  const requestApiKeyOtpMutation = useMutation({
    mutationFn: (email: string) => organizationsApi.requestOtp(email, 'login'),
    onSuccess: () => {
      toast.success('OTP sent to your email');
      setApiKeyStep('otp');
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to send OTP');
    },
  });

  // Create API key mutation
  const createApiKeyMutation = useMutation({
    mutationFn: async ({ orgId, email, otpCode, keyName }: { orgId: string; email: string; otpCode: string; keyName?: string }) => {
      return organizationsApi.createApiKey(orgId, {
        contact_email: email,
        otp_code: otpCode,
        key_name: keyName,
      });
    },
    onSuccess: (response) => {
      const data = response.data; // Backend returns { success, message, api_key, key_prefix, expires_at }
      toast.success('API key created successfully');
      setNewApiKey(data.api_key);
      setIsCreateApiKeyDialogOpen(true);
      // Update logged in org with new API key info (prefix only)
      if (loggedInOrg) {
        setLoggedInOrg({
          ...loggedInOrg,
          api_keys: [
            ...(loggedInOrg.api_keys || []),
            {
              id: 'new',
              key_prefix: data.key_prefix,
              name: apiKeyName || 'Unnamed',
              expires_at: data.expires_at,
            },
          ],
        });
      }
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to create API key');
    },
  });

  const handleRegister = (e: React.FormEvent) => {
    e.preventDefault();
    if (regStep === 'email') {
      if (!regEmail) {
        toast.error('Please enter your email');
        return;
      }
      requestRegOtpMutation.mutate(regEmail);
    } else {
      if (!regOtpCode || regOtpCode.length !== 6) {
        toast.error('Please enter a valid 6-digit OTP code');
        return;
      }
      if (!regName || !regSlug) {
        toast.error('Please fill in all fields');
        return;
      }
      registerMutation.mutate({
        name: regName,
        slug: regSlug,
        contact_email: regEmail,
        otp_code: regOtpCode,
      });
    }
  };

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    if (loginStep === 'email') {
      if (!loginEmail) {
        toast.error('Please enter your email');
        return;
      }
      requestLoginOtpMutation.mutate(loginEmail);
    } else {
      if (!loginOtpCode || loginOtpCode.length !== 6) {
        toast.error('Please enter a valid 6-digit OTP code');
        return;
      }
      loginMutation.mutate({
        contact_email: loginEmail,
        otp_code: loginOtpCode,
      });
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast.success('Copied to clipboard');
  };

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
              <Building2 className="h-8 w-8" />
              Organization Management
            </h1>
            <p className="text-muted-foreground">
              Register, login, and manage organizations for API access
            </p>
          </div>
          <div className="flex gap-2">
            <Dialog open={isRegisterDialogOpen} onOpenChange={setIsRegisterDialogOpen}>
              <DialogTrigger asChild>
                <Button variant="outline">
                  <Plus className="mr-2 h-4 w-4" />
                  Register Organization
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Register New Organization</DialogTitle>
                  <DialogDescription>
                    Create a new organization account to access the API
                  </DialogDescription>
                </DialogHeader>
                <form onSubmit={handleRegister}>
                  {regStep === 'email' ? (
                    <div className="space-y-4 py-4">
                      <div className="space-y-2">
                        <Label htmlFor="reg-email">Contact Email</Label>
                        <Input
                          id="reg-email"
                          type="email"
                          value={regEmail}
                          onChange={(e) => setRegEmail(e.target.value)}
                          placeholder="contact@organization.com"
                          required
                        />
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-4 py-4">
                      <div className="space-y-2">
                        <Label>Email</Label>
                        <Input value={regEmail} disabled className="bg-muted" />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="reg-name">Organization Name</Label>
                        <Input
                          id="reg-name"
                          value={regName}
                          onChange={(e) => setRegName(e.target.value)}
                          placeholder="My Organization"
                          required
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="reg-slug">Slug (URL-friendly)</Label>
                        <Input
                          id="reg-slug"
                          value={regSlug}
                          onChange={(e) => setRegSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ''))}
                          placeholder="my-organization"
                          required
                        />
                        <p className="text-xs text-muted-foreground">
                          Lowercase letters, numbers, and hyphens only
                        </p>
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="reg-otp">OTP Code</Label>
                        <Input
                          id="reg-otp"
                          type="text"
                          value={regOtpCode}
                          onChange={(e) => {
                            const value = e.target.value.replace(/\D/g, '').slice(0, 6);
                            setRegOtpCode(value);
                          }}
                          placeholder="000000"
                          maxLength={6}
                          className="text-center text-2xl tracking-widest"
                          required
                        />
                      </div>
                    </div>
                  )}
                  <DialogFooter>
                    {regStep === 'otp' && (
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() => {
                          setRegStep('email');
                          setRegOtpCode('');
                        }}
                      >
                        Back
                      </Button>
                    )}
                    <Button type="submit" disabled={requestRegOtpMutation.isPending || registerMutation.isPending}>
                      {requestRegOtpMutation.isPending || registerMutation.isPending ? (
                        <>
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          {regStep === 'email' ? 'Sending...' : 'Registering...'}
                        </>
                      ) : (
                        regStep === 'email' ? 'Send OTP' : 'Register'
                      )}
                    </Button>
                  </DialogFooter>
                </form>
              </DialogContent>
            </Dialog>
            <Dialog open={isLoginDialogOpen} onOpenChange={setIsLoginDialogOpen}>
              <DialogTrigger asChild>
                <Button>
                  <Key className="mr-2 h-4 w-4" />
                  Login Organization
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Login Organization</DialogTitle>
                  <DialogDescription>
                    Login to manage your organization's API keys
                  </DialogDescription>
                </DialogHeader>
                <form onSubmit={handleLogin}>
                  {loginStep === 'email' ? (
                    <div className="space-y-4 py-4">
                      <div className="space-y-2">
                        <Label htmlFor="login-email">Contact Email</Label>
                        <Input
                          id="login-email"
                          type="email"
                          value={loginEmail}
                          onChange={(e) => setLoginEmail(e.target.value)}
                          placeholder="contact@organization.com"
                          required
                        />
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-4 py-4">
                      <div className="space-y-2">
                        <Label>Email</Label>
                        <Input value={loginEmail} disabled className="bg-muted" />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="login-otp">OTP Code</Label>
                        <Input
                          id="login-otp"
                          type="text"
                          value={loginOtpCode}
                          onChange={(e) => {
                            const value = e.target.value.replace(/\D/g, '').slice(0, 6);
                            setLoginOtpCode(value);
                          }}
                          placeholder="000000"
                          maxLength={6}
                          className="text-center text-2xl tracking-widest"
                          required
                        />
                      </div>
                    </div>
                  )}
                  <DialogFooter>
                    {loginStep === 'otp' && (
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() => {
                          setLoginStep('email');
                          setLoginOtpCode('');
                        }}
                      >
                        Back
                      </Button>
                    )}
                    <Button type="submit" disabled={requestLoginOtpMutation.isPending || loginMutation.isPending}>
                      {requestLoginOtpMutation.isPending || loginMutation.isPending ? (
                        <>
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          {loginStep === 'email' ? 'Sending...' : 'Logging in...'}
                        </>
                      ) : (
                        loginStep === 'email' ? 'Send OTP' : 'Login'
                      )}
                    </Button>
                  </DialogFooter>
                </form>
              </DialogContent>
            </Dialog>
          </div>
        </div>

        {/* Tabs */}
        <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as 'admin' | 'self-service')}>
          <TabsList>
            <TabsTrigger value="admin">Admin View</TabsTrigger>
            <TabsTrigger value="self-service">Self-Service</TabsTrigger>
          </TabsList>

          <TabsContent value="admin" className="space-y-6">
            {/* Organizations Table */}
            <Card>
              <CardHeader>
                <CardTitle>All Organizations</CardTitle>
                <CardDescription>
                  View and manage all registered organizations
                </CardDescription>
              </CardHeader>
              <CardContent>
                {isLoadingOrgs ? (
                  <div className="text-center py-8">
                    <Loader2 className="h-8 w-8 animate-spin mx-auto mb-4" />
                    <p className="text-muted-foreground">Loading organizations...</p>
                  </div>
                ) : organizations.length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground">
                    No organizations registered yet.
                  </div>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Name</TableHead>
                        <TableHead>Slug</TableHead>
                        <TableHead>Contact Email</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Rate Limit</TableHead>
                        <TableHead>Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {organizations.map((org: any) => (
                        <TableRow key={org.id}>
                          <TableCell className="font-medium">{org.name}</TableCell>
                          <TableCell className="font-mono text-sm">{org.slug}</TableCell>
                          <TableCell>{org.contact_email || '-'}</TableCell>
                          <TableCell>
                            <Badge variant={org.is_active ? 'default' : 'secondary'}>
                              {org.is_active ? 'Active' : 'Inactive'}
                            </Badge>
                          </TableCell>
                          <TableCell>{org.rate_limit_per_hour}/hour</TableCell>
                          <TableCell>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => setSelectedOrgId(org.id)}
                            >
                              View API Keys
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="self-service" className="space-y-6">
            {loggedInOrg ? (
              <Card>
                <CardHeader>
                  <CardTitle>Logged in as {loggedInOrg.name}</CardTitle>
                  <CardDescription>
                    Manage your organization's API keys
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <p className="text-sm text-muted-foreground">Organization ID</p>
                        <p className="font-mono text-sm">{loggedInOrg.id}</p>
                      </div>
                      <div>
                        <p className="text-sm text-muted-foreground">Slug</p>
                        <p className="font-mono text-sm">{loggedInOrg.slug}</p>
                      </div>
                    </div>
                    {loggedInOrg?.api_keys && loggedInOrg.api_keys.length > 0 && (
                      <div>
                        <p className="text-sm font-medium mb-2">Your API Keys</p>
                        <div className="space-y-2">
                          {loggedInOrg.api_keys.map((key: any) => (
                            <div key={key.id} className="flex items-center justify-between p-2 border rounded">
                              <div>
                                <p className="font-mono text-sm">{key.key_prefix}...</p>
                                <p className="text-xs text-muted-foreground">{key.name || 'Unnamed'}</p>
                                {key.expires_at && (
                                  <p className="text-xs text-muted-foreground">
                                    Expires: {new Date(key.expires_at).toLocaleDateString()}
                                  </p>
                                )}
                              </div>
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => copyToClipboard(key.key_prefix)}
                              >
                                <Copy className="h-4 w-4" />
                              </Button>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    <Dialog open={isCreateApiKeyDialogOpen} onOpenChange={setIsCreateApiKeyDialogOpen}>
                      <DialogTrigger asChild>
                        <Button onClick={() => {
                          setApiKeyOtpEmail(loggedInOrg.contact_email);
                          setApiKeyStep('email');
                        }}>
                          <Plus className="mr-2 h-4 w-4" />
                          Create API Key
                        </Button>
                      </DialogTrigger>
                      <DialogContent>
                        <DialogHeader>
                          <DialogTitle>Create API Key</DialogTitle>
                          <DialogDescription>
                            Create a new API key for {loggedInOrg.name}
                          </DialogDescription>
                        </DialogHeader>
                        {newApiKey ? (
                          <div className="space-y-4 py-4">
                            <div className="p-4 bg-muted rounded-lg">
                              <Label className="text-sm text-muted-foreground">API Key (Copy this now - it won't be shown again)</Label>
                              <div className="flex items-center gap-2 mt-2">
                                <Input
                                  value={newApiKey}
                                  readOnly
                                  className="font-mono text-sm"
                                />
                                <Button
                                  variant="outline"
                                  size="icon"
                                  onClick={() => copyToClipboard(newApiKey)}
                                >
                                  <Copy className="h-4 w-4" />
                                </Button>
                              </div>
                            </div>
                            <div className="p-4 border border-yellow-500 rounded-lg bg-yellow-50 dark:bg-yellow-900/20">
                              <p className="text-sm text-yellow-800 dark:text-yellow-200">
                                ⚠️ Important: Save this API key securely. You won't be able to see it again.
                              </p>
                            </div>
                            <DialogFooter>
                              <Button
                                onClick={() => {
                                  setNewApiKey(null);
                                  setApiKeyOtpEmail('');
                                  setApiKeyOtpCode('');
                                  setApiKeyName('');
                                  setApiKeyStep('email');
                                  setIsCreateApiKeyDialogOpen(false);
                                }}
                              >
                                I've Saved It
                              </Button>
                            </DialogFooter>
                          </div>
                        ) : (
                          <form onSubmit={(e) => {
                            e.preventDefault();
                            if (apiKeyStep === 'email') {
                              if (!apiKeyOtpEmail) {
                                toast.error('Please enter your email');
                                return;
                              }
                              requestApiKeyOtpMutation.mutate(apiKeyOtpEmail);
                            } else {
                              if (!apiKeyOtpCode || apiKeyOtpCode.length !== 6) {
                                toast.error('Please enter a valid 6-digit OTP code');
                                return;
                              }
                              if (!loggedInOrg?.id) {
                                toast.error('Organization not found');
                                return;
                              }
                              createApiKeyMutation.mutate({
                                orgId: loggedInOrg.id,
                                email: apiKeyOtpEmail,
                                otpCode: apiKeyOtpCode,
                                keyName: apiKeyName.trim() || undefined,
                              });
                            }
                          }}>
                            {apiKeyStep === 'email' ? (
                              <div className="space-y-4 py-4">
                                <div className="space-y-2">
                                  <Label htmlFor="api-key-email">Contact Email</Label>
                                  <Input
                                    id="api-key-email"
                                    type="email"
                                    value={apiKeyOtpEmail}
                                    onChange={(e) => setApiKeyOtpEmail(e.target.value)}
                                    placeholder="contact@organization.com"
                                    required
                                  />
                                </div>
                              </div>
                            ) : (
                              <div className="space-y-4 py-4">
                                <div className="space-y-2">
                                  <Label>Email</Label>
                                  <Input value={apiKeyOtpEmail} disabled className="bg-muted" />
                                </div>
                                <div className="space-y-2">
                                  <Label htmlFor="api-key-name">Key Name (Optional)</Label>
                                  <Input
                                    id="api-key-name"
                                    value={apiKeyName}
                                    onChange={(e) => setApiKeyName(e.target.value)}
                                    placeholder="Production API Key"
                                  />
                                </div>
                                <div className="space-y-2">
                                  <Label htmlFor="api-key-otp">OTP Code</Label>
                                  <Input
                                    id="api-key-otp"
                                    type="text"
                                    value={apiKeyOtpCode}
                                    onChange={(e) => {
                                      const value = e.target.value.replace(/\D/g, '').slice(0, 6);
                                      setApiKeyOtpCode(value);
                                    }}
                                    placeholder="000000"
                                    maxLength={6}
                                    className="text-center text-2xl tracking-widest"
                                    required
                                  />
                                </div>
                              </div>
                            )}
                            <DialogFooter>
                              {apiKeyStep === 'otp' && (
                                <Button
                                  type="button"
                                  variant="outline"
                                  onClick={() => {
                                    setApiKeyStep('email');
                                    setApiKeyOtpCode('');
                                  }}
                                >
                                  Back
                                </Button>
                              )}
                              <Button
                                type="submit"
                                disabled={requestApiKeyOtpMutation.isPending || createApiKeyMutation.isPending}
                              >
                                {requestApiKeyOtpMutation.isPending || createApiKeyMutation.isPending ? (
                                  <>
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    {apiKeyStep === 'email' ? 'Sending...' : 'Creating...'}
                                  </>
                                ) : (
                                  apiKeyStep === 'email' ? 'Send OTP' : 'Create Key'
                                )}
                              </Button>
                            </DialogFooter>
                          </form>
                        )}
                      </DialogContent>
                    </Dialog>
                  </div>
                </CardContent>
              </Card>
            ) : (
              <Card>
                <CardHeader>
                  <CardTitle>Self-Service Portal</CardTitle>
                  <CardDescription>
                    Register or login to manage your organization's API keys
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="text-center py-8 text-muted-foreground">
                    Please register or login to manage your organization.
                  </div>
                </CardContent>
              </Card>
            )}
          </TabsContent>
        </Tabs>
      </div>
    </DashboardLayout>
  );
}

export default function OrganizationsPage() {
  return (
    <ProtectedRoute allowedRoles={['admin', 'superadmin', 'organization_admin']}>
      <OrganizationsContent />
    </ProtectedRoute>
  );
}
