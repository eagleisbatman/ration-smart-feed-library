'use client';

import { useState } from 'react';
import { useTranslations } from '@/hooks/use-translations';
import { DashboardLayout } from '@/components/layout/dashboard-layout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { countriesApi, superadminApi, auth } from '@/lib/api';
import { toast } from 'sonner';
import { Plus, Users, Shield, Trash2, Mail } from 'lucide-react';
import React from 'react';
import { ProtectedRoute } from '@/components/auth/protected-route';

function SuperadminContent() {
  const t = useTranslations('superadmin');
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [adminEmail, setAdminEmail] = useState('');
  const [adminName, setAdminName] = useState('');
  const [selectedCountryId, setSelectedCountryId] = useState('');

  const queryClient = useQueryClient();
  const user = auth.getCurrentUser();
  const superadminEmail = user?.email_id || '';

  // Fetch countries
  const { data: countries = [] } = useQuery({
    queryKey: ['countries'],
    queryFn: () => countriesApi.getAll().then(res => res.data),
  });

  // Fetch country admins
  const { data: countryAdmins = [], isLoading } = useQuery({
    queryKey: ['country-admins', superadminEmail],
    queryFn: () => superadminApi.listCountryAdmins(superadminEmail).then(res => res.data),
    enabled: !!superadminEmail,
  });

  // Create country admin mutation
  const createAdminMutation = useMutation({
    mutationFn: async (data: {
      admin_email: string;
      admin_name: string;
      country_id: string;
      superadmin_email: string;
    }) => {
      return superadminApi.createCountryAdmin(data).then(res => res.data);
    },
    onSuccess: () => {
      toast.success('Country admin created successfully');
      setIsCreateDialogOpen(false);
      setAdminEmail('');
      setAdminName('');
      setSelectedCountryId('');
      queryClient.invalidateQueries({ queryKey: ['country-admins'] });
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to create country admin');
    },
  });

  // Remove country admin mutation
  const removeAdminMutation = useMutation({
    mutationFn: async (adminId: string) => {
      return superadminApi.removeCountryAdmin(adminId, superadminEmail).then(res => res.data);
    },
    onSuccess: () => {
      toast.success('Country admin removed successfully');
      queryClient.invalidateQueries({ queryKey: ['country-admins'] });
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to remove country admin');
    },
  });

  const handleCreateAdmin = (e: React.FormEvent) => {
    e.preventDefault();
    if (!adminEmail || !adminName || !selectedCountryId || !superadminEmail) {
      toast.error('Please fill in all fields');
      return;
    }
    createAdminMutation.mutate({
      admin_email: adminEmail,
      admin_name: adminName,
      country_id: selectedCountryId,
      superadmin_email: superadminEmail,
    });
  };

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
              <Shield className="h-8 w-8" />
              Superadmin Dashboard
            </h1>
            <p className="text-muted-foreground">
              Manage country-level administrators and system settings
            </p>
          </div>
          <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="mr-2 h-4 w-4" />
                Create Country Admin
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Create Country Admin</DialogTitle>
                <DialogDescription>
                  Create a new country-level administrator who can manage feeds for a specific country
                </DialogDescription>
              </DialogHeader>
              <form onSubmit={handleCreateAdmin}>
                <div className="space-y-4 py-4">
                  <div className="space-y-2">
                    <Label htmlFor="admin-name">Admin Name</Label>
                    <Input
                      id="admin-name"
                      value={adminName}
                      onChange={(e) => setAdminName(e.target.value)}
                      placeholder="John Doe"
                      required
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="admin-email">Admin Email</Label>
                    <Input
                      id="admin-email"
                      type="email"
                      value={adminEmail}
                      onChange={(e) => setAdminEmail(e.target.value)}
                      placeholder="admin@example.com"
                      required
                    />
                    <p className="text-xs text-muted-foreground">
                      An OTP will be sent to this email for first login
                    </p>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="country">Country</Label>
                    <Select value={selectedCountryId} onValueChange={setSelectedCountryId} required>
                      <SelectTrigger>
                        <SelectValue placeholder="Select a country" />
                      </SelectTrigger>
                      <SelectContent>
                        {countries.map((country: any) => (
                          <SelectItem key={country.id} value={country.id}>
                            {country.name} ({country.country_code})
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <DialogFooter>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setIsCreateDialogOpen(false)}
                  >
                    Cancel
                  </Button>
                  <Button type="submit" disabled={createAdminMutation.isPending}>
                    {createAdminMutation.isPending ? 'Creating...' : 'Create Admin'}
                  </Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        </div>

        {/* Stats */}
        <div className="grid gap-4 md:grid-cols-3">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Country Admins</CardTitle>
              <Users className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {countryAdmins?.admins?.length || 0}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Active Countries</CardTitle>
              <Shield className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {new Set(countryAdmins?.admins?.map((a: any) => a.country_id)).size || 0}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Countries</CardTitle>
              <Mail className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{countries.length}</div>
            </CardContent>
          </Card>
        </div>

        {/* Country Admins Table */}
        <Card>
          <CardHeader>
            <CardTitle>Country Administrators</CardTitle>
            <CardDescription>
              Manage country-level administrators and their assigned countries
            </CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="text-center py-8 text-muted-foreground">Loading...</div>
            ) : countryAdmins?.admins?.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                No country admins created yet. Create one to get started.
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Email</TableHead>
                    <TableHead>Country</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {countryAdmins?.admins?.map((admin: any) => (
                    <TableRow key={admin.id}>
                      <TableCell className="font-medium">{admin.name}</TableCell>
                      <TableCell>{admin.email}</TableCell>
                      <TableCell>
                        <Badge variant="outline">{admin.country_name}</Badge>
                      </TableCell>
                      <TableCell>
                        <Badge variant={admin.is_active ? 'default' : 'secondary'}>
                          {admin.is_active ? 'Active' : 'Inactive'}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            if (confirm(`Remove ${admin.name} as country admin?`)) {
                              removeAdminMutation.mutate(admin.id);
                            }
                          }}
                          disabled={removeAdminMutation.isPending}
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}

export default function SuperadminPage() {
  return (
    <ProtectedRoute allowedRoles={['superadmin']}>
      <SuperadminContent />
    </ProtectedRoute>
  );
}

