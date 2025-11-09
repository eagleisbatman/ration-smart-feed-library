'use client';

import { useState } from 'react';
import { useTranslations } from '@/hooks/use-translations';
import { DashboardLayout } from '@/components/layout/dashboard-layout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
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
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { feedsApi, countriesApi } from '@/lib/api';
import { auth } from '@/lib/auth';
import { toast } from 'sonner';
import { Plus, Search, Download, Upload, Edit, Trash2, Globe, Loader2 } from 'lucide-react';
import { FeedForm } from '@/components/feeds/feed-form';
import { useRouter } from 'next/navigation';

export default function FeedsPage() {
  const t = useTranslations('feeds');
  const router = useRouter();
  const queryClient = useQueryClient();
  const user = auth.getCurrentUser();
  
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCountry, setSelectedCountry] = useState<string>('all');
  const [selectedType, setSelectedType] = useState<string>('all');
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const [editingFeedId, setEditingFeedId] = useState<string | null>(null);
  const [deletingFeedId, setDeletingFeedId] = useState<string | null>(null);

  // Redirect if not authenticated
  if (!user) {
    router.push('/login');
    return null;
  }

  // Fetch feeds
  const { data: feedsResponse, isLoading } = useQuery({
    queryKey: ['feeds', selectedCountry, selectedType],
    queryFn: () => feedsApi.getAll({
      country_id: selectedCountry !== 'all' ? selectedCountry : undefined,
      feed_type: selectedType !== 'all' ? selectedType : undefined,
      limit: 1000,
    }).then(res => res.data),
  });
  
  // Extract feeds array from paginated response or use direct array
  const feeds = Array.isArray(feedsResponse) 
    ? feedsResponse 
    : (feedsResponse?.feeds || []);

  // Fetch countries
  const { data: countries = [] } = useQuery({
    queryKey: ['countries'],
    queryFn: () => countriesApi.getAll().then(res => res.data),
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: async (feedId: string) => {
      if (!user?.id) throw new Error('User not authenticated');
      return feedsApi.delete(feedId, user.id);
    },
    onSuccess: () => {
      toast.success('Feed deleted successfully');
      queryClient.invalidateQueries({ queryKey: ['feeds'] });
      setDeletingFeedId(null);
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to delete feed');
    },
  });

  // Filter feeds by search query
  const filteredFeeds = feeds.filter((feed: any) => {
    const name = feed.fd_name || feed.fd_name_default || '';
    const code = feed.fd_code || '';
    const searchLower = searchQuery.toLowerCase();
    return name.toLowerCase().includes(searchLower) || code.toLowerCase().includes(searchLower);
  });

  const handleEdit = (feedId: string) => {
    setEditingFeedId(feedId);
  };

  const handleDelete = (feedId: string) => {
    setDeletingFeedId(feedId);
  };

  const confirmDelete = () => {
    if (deletingFeedId) {
      deleteMutation.mutate(deletingFeedId);
    }
  };

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Feed Management</h1>
            <p className="text-muted-foreground">
              Manage feeds across all countries with multi-language support
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => {
              const input = document.createElement('input');
              input.type = 'file';
              input.accept = '.xls,.xlsx';
              input.onchange = async (e: any) => {
                const file = e.target.files[0];
                if (file && user?.id) {
                  try {
                    await feedsApi.bulkImport(file, user.id);
                    toast.success('Bulk import started');
                    queryClient.invalidateQueries({ queryKey: ['feeds'] });
                  } catch (error: any) {
                    toast.error(error.response?.data?.detail || 'Bulk import failed');
                  }
                }
              };
              input.click();
            }}>
              <Upload className="mr-2 h-4 w-4" />
              Bulk Import
            </Button>
            <Button onClick={() => setIsAddDialogOpen(true)}>
              <Plus className="mr-2 h-4 w-4" />
              Add Feed
            </Button>
          </div>
        </div>

        {/* Filters */}
        <Card>
          <CardHeader>
            <CardTitle>Filters</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex gap-4">
              <div className="flex-1">
                <div className="relative">
                  <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Search feeds by name or code..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-8"
                  />
                </div>
              </div>
              <Select value={selectedCountry} onValueChange={setSelectedCountry}>
                <SelectTrigger className="w-[200px]">
                  <SelectValue placeholder="All Countries" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Countries</SelectItem>
                  {countries.map((country: any) => (
                    <SelectItem key={country.id} value={country.id}>
                      {country.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select value={selectedType} onValueChange={setSelectedType}>
                <SelectTrigger className="w-[180px]">
                  <SelectValue placeholder="All Types" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Types</SelectItem>
                  <SelectItem value="Forage">Forage</SelectItem>
                  <SelectItem value="Concentrate">Concentrate</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </CardContent>
        </Card>

        {/* Feeds Table */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Feeds</CardTitle>
                <CardDescription>
                  {filteredFeeds.length} feed{filteredFeeds.length !== 1 ? 's' : ''} found
                </CardDescription>
              </div>
              <Button variant="outline" size="sm">
                <Download className="mr-2 h-4 w-4" />
                Export
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="text-center py-8">
                <Loader2 className="h-8 w-8 animate-spin mx-auto mb-4" />
                <p className="text-muted-foreground">Loading feeds...</p>
              </div>
            ) : filteredFeeds.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                {searchQuery ? 'No feeds match your search' : 'No feeds found. Add your first feed to get started.'}
              </div>
            ) : (
              <div className="rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Code</TableHead>
                      <TableHead>Name</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Category</TableHead>
                      <TableHead>Country</TableHead>
                      <TableHead>DM (%)</TableHead>
                      <TableHead>CP (%)</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredFeeds.map((feed: any) => (
                      <TableRow key={feed.feed_id || feed.id}>
                        <TableCell className="font-mono text-sm">
                          {feed.fd_code}
                        </TableCell>
                        <TableCell className="font-medium">
                          <div className="flex items-center gap-2">
                            {feed.fd_name_default || feed.fd_name}
                            {feed.names && Object.keys(feed.names).length > 1 && (
                              <Badge variant="outline" className="text-xs">
                                <Globe className="h-3 w-3 mr-1" />
                                {Object.keys(feed.names).length} langs
                              </Badge>
                            )}
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge variant={feed.fd_type === 'Forage' ? 'default' : 'secondary'}>
                            {feed.fd_type}
                          </Badge>
                        </TableCell>
                        <TableCell>{feed.fd_category || '-'}</TableCell>
                        <TableCell>{feed.fd_country_name || '-'}</TableCell>
                        <TableCell>{feed.fd_dm ? parseFloat(feed.fd_dm).toFixed(1) : '-'}</TableCell>
                        <TableCell>{feed.fd_cp ? parseFloat(feed.fd_cp).toFixed(1) : '-'}</TableCell>
                        <TableCell className="text-right">
                          <div className="flex justify-end gap-2">
                            <Button 
                              variant="ghost" 
                              size="icon"
                              onClick={() => handleEdit(feed.feed_id || feed.id)}
                            >
                              <Edit className="h-4 w-4" />
                            </Button>
                            <Button 
                              variant="ghost" 
                              size="icon"
                              onClick={() => handleDelete(feed.feed_id || feed.id)}
                            >
                              <Trash2 className="h-4 w-4 text-destructive" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Add Feed Dialog */}
        <FeedForm
          open={isAddDialogOpen}
          onOpenChange={setIsAddDialogOpen}
        />

        {/* Edit Feed Dialog */}
        {editingFeedId && (
          <FeedForm
            open={!!editingFeedId}
            onOpenChange={(open) => {
              if (!open) setEditingFeedId(null);
            }}
            feedId={editingFeedId}
          />
        )}

        {/* Delete Confirmation Dialog */}
        <AlertDialog open={!!deletingFeedId} onOpenChange={(open) => !open && setDeletingFeedId(null)}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Are you sure?</AlertDialogTitle>
              <AlertDialogDescription>
                This action cannot be undone. This will permanently delete the feed from the database.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel disabled={deleteMutation.isPending}>Cancel</AlertDialogCancel>
              <AlertDialogAction
                onClick={confirmDelete}
                disabled={deleteMutation.isPending}
                className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              >
                {deleteMutation.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Deleting...
                  </>
                ) : (
                  'Delete'
                )}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </DashboardLayout>
  );
}
