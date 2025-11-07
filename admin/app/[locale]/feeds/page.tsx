'use client';

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
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Link } from '@/lib/navigation';
import { useQuery } from '@tanstack/react-query';
import { feedsApi, countriesApi } from '@/lib/api';
import { useState } from 'react';
import { Plus, Search, Filter, Download, Upload, Edit, Trash2, Globe } from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

export default function FeedsPage() {
  const t = useTranslations('feeds');
  const tCommon = useTranslations('common');
  
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCountry, setSelectedCountry] = useState<string>('all');
  const [selectedType, setSelectedType] = useState<string>('all');
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);

  // Fetch feeds
  const { data: feeds = [], isLoading } = useQuery({
    queryKey: ['feeds', selectedCountry, selectedType, searchQuery],
    queryFn: () => feedsApi.getAll({
      country_id: selectedCountry !== 'all' ? selectedCountry : undefined,
      feed_type: selectedType !== 'all' ? selectedType : undefined,
      limit: 100,
    }).then(res => res.data),
  });

  // Fetch countries
  const { data: countries = [] } = useQuery({
    queryKey: ['countries'],
    queryFn: () => countriesApi.getAll().then(res => res.data),
  });

  // Filter feeds by search query
  const filteredFeeds = feeds.filter((feed: any) =>
    feed.fd_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    feed.fd_code?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">{t('title')}</h1>
            <p className="text-muted-foreground">
              Manage feeds across all countries with multi-language support
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" asChild>
              <Link href="/feeds/import">
                <Upload className="mr-2 h-4 w-4" />
                {t('bulkImport')}
              </Link>
            </Button>
            <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
              <DialogTrigger asChild>
                <Button>
                  <Plus className="mr-2 h-4 w-4" />
                  {t('addFeed')}
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-2xl">
                <DialogHeader>
                  <DialogTitle>{t('addFeed')}</DialogTitle>
                  <DialogDescription>
                    Add a new feed with nutritional information
                  </DialogDescription>
                </DialogHeader>
                <AddFeedForm
                  countries={countries}
                  onSuccess={() => setIsAddDialogOpen(false)}
                />
              </DialogContent>
            </Dialog>
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
                    placeholder={tCommon('search')}
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
                  {filteredFeeds.length} feeds found
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
              <div className="text-center py-8 text-muted-foreground">
                {tCommon('loading')}
              </div>
            ) : filteredFeeds.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                No feeds found. Add your first feed to get started.
              </div>
            ) : (
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
                          {feed.fd_name}
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
                      <TableCell>{feed.fd_dm?.toFixed(1) || '-'}</TableCell>
                      <TableCell>{feed.fd_cp?.toFixed(1) || '-'}</TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-2">
                          <Button variant="ghost" size="icon">
                            <Edit className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="icon">
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
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

function AddFeedForm({ countries, onSuccess }: { countries: any[]; onSuccess: () => void }) {
  const [formData, setFormData] = useState({
    fd_code: '',
    fd_name: '',
    fd_type: 'Forage',
    fd_category: '',
    fd_country_id: '',
    fd_dm: '',
    fd_cp: '',
    fd_ndf: '',
    fd_adf: '',
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    // TODO: Implement feed creation
    console.log('Creating feed:', formData);
    onSuccess();
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <Tabs defaultValue="basic" className="w-full">
        <TabsList>
          <TabsTrigger value="basic">Basic Info</TabsTrigger>
          <TabsTrigger value="nutritional">Nutritional Values</TabsTrigger>
          <TabsTrigger value="translations">Translations</TabsTrigger>
        </TabsList>
        
        <TabsContent value="basic" className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="code">Feed Code</Label>
              <Input
                id="code"
                value={formData.fd_code}
                onChange={(e) => setFormData({ ...formData, fd_code: e.target.value })}
                required
              />
            </div>
            <div>
              <Label htmlFor="country">Country</Label>
              <Select
                value={formData.fd_country_id}
                onValueChange={(value) => setFormData({ ...formData, fd_country_id: value })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select country" />
                </SelectTrigger>
                <SelectContent>
                  {countries.map((country) => (
                    <SelectItem key={country.id} value={country.id}>
                      {country.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div>
            <Label htmlFor="name">Feed Name (English)</Label>
            <Input
              id="name"
              value={formData.fd_name}
              onChange={(e) => setFormData({ ...formData, fd_name: e.target.value })}
              required
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="type">Type</Label>
              <Select
                value={formData.fd_type}
                onValueChange={(value) => setFormData({ ...formData, fd_type: value })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="Forage">Forage</SelectItem>
                  <SelectItem value="Concentrate">Concentrate</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label htmlFor="category">Category</Label>
              <Input
                id="category"
                value={formData.fd_category}
                onChange={(e) => setFormData({ ...formData, fd_category: e.target.value })}
              />
            </div>
          </div>
        </TabsContent>

        <TabsContent value="nutritional" className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="dm">Dry Matter (%)</Label>
              <Input
                id="dm"
                type="number"
                step="0.01"
                value={formData.fd_dm}
                onChange={(e) => setFormData({ ...formData, fd_dm: e.target.value })}
              />
            </div>
            <div>
              <Label htmlFor="cp">Crude Protein (%)</Label>
              <Input
                id="cp"
                type="number"
                step="0.01"
                value={formData.fd_cp}
                onChange={(e) => setFormData({ ...formData, fd_cp: e.target.value })}
              />
            </div>
            <div>
              <Label htmlFor="ndf">NDF (%)</Label>
              <Input
                id="ndf"
                type="number"
                step="0.01"
                value={formData.fd_ndf}
                onChange={(e) => setFormData({ ...formData, fd_ndf: e.target.value })}
              />
            </div>
            <div>
              <Label htmlFor="adf">ADF (%)</Label>
              <Input
                id="adf"
                type="number"
                step="0.01"
                value={formData.fd_adf}
                onChange={(e) => setFormData({ ...formData, fd_adf: e.target.value })}
              />
            </div>
          </div>
        </TabsContent>

        <TabsContent value="translations" className="space-y-4">
          <div className="text-sm text-muted-foreground">
            Translations will be managed in Traduora. After creating the feed, you can add translations
            for other languages in the Traduora interface.
          </div>
        </TabsContent>
      </Tabs>

      <DialogFooter>
        <Button type="button" variant="outline" onClick={onSuccess}>
          {tCommon('cancel')}
        </Button>
        <Button type="submit">{tCommon('save')}</Button>
      </DialogFooter>
    </form>
  );
}

