'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { countryAdminFeedsApi, countriesApi } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
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
import { Loader2, Plus, Trash2, Globe, ExternalLink } from 'lucide-react';
import { toast } from 'sonner';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

interface FeedTranslationsTabProps {
  feedId?: string;
  feedName: string;
  countryId: string;
  translations: any[];
  userEmail: string;
  isEdit: boolean;
}

export function FeedTranslationsTab({
  feedId,
  feedName,
  countryId,
  translations,
  userEmail,
  isEdit,
}: FeedTranslationsTabProps) {
  const queryClient = useQueryClient();
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const [newLanguage, setNewLanguage] = useState('');
  const [newTranslation, setNewTranslation] = useState('');

  // Fetch country languages
  const { data: countries = [] } = useQuery({
    queryKey: ['countries'],
    queryFn: () => countriesApi.getAll().then(res => res.data),
  });

  const currentCountry = countries.find((c: any) => c.id === countryId);
  const supportedLanguages = currentCountry?.supported_languages || ['en'];
  const countryLanguages = currentCountry?.country_languages || [];

  // Add translation mutation
  const addTranslationMutation = useMutation({
    mutationFn: async (data: { language_code: string; translation_text: string }) => {
      if (!feedId || !userEmail) throw new Error('Feed ID or user email missing');
      return countryAdminFeedsApi.addTranslation(userEmail, feedId, data);
    },
    onSuccess: () => {
      toast.success('Translation added successfully');
      queryClient.invalidateQueries({ queryKey: ['feed-translations', feedId] });
      setIsAddDialogOpen(false);
      setNewLanguage('');
      setNewTranslation('');
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to add translation');
    },
  });

  const handleAddTranslation = () => {
    if (!newLanguage || !newTranslation.trim()) {
      toast.error('Please fill in all fields');
      return;
    }
    addTranslationMutation.mutate({
      language_code: newLanguage,
      translation_text: newTranslation.trim(),
    });
  };

  const traduoraUrl = process.env.NEXT_PUBLIC_TRADUORA_URL;
  const hasTraduora = !!traduoraUrl;

  if (!isEdit) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        <Globe className="h-12 w-12 mx-auto mb-4 opacity-50" />
        <p className="text-sm">
          Save the feed first to add translations in multiple languages.
        </p>
        {hasTraduora && (
          <p className="text-xs mt-2">
            Translations can also be managed in{' '}
            <a
              href={traduoraUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline inline-flex items-center gap-1"
            >
              Traduora <ExternalLink className="h-3 w-3" />
            </a>
          </p>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold flex items-center gap-2">
            <Globe className="h-5 w-5" />
            Feed Translations
          </h3>
          <p className="text-sm text-muted-foreground">
            Add translations for feed name: <strong>{feedName}</strong>
          </p>
        </div>
        <div className="flex gap-2">
          {hasTraduora && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => window.open(traduoraUrl, '_blank')}
            >
              <ExternalLink className="mr-2 h-4 w-4" />
              Open Traduora
            </Button>
          )}
          <Button
            size="sm"
            onClick={() => setIsAddDialogOpen(true)}
            disabled={!feedId || !countryId}
          >
            <Plus className="mr-2 h-4 w-4" />
            Add Translation
          </Button>
        </div>
      </div>

      {!countryId ? (
        <div className="text-center py-8 text-muted-foreground">
          <p className="text-sm">Please select a country first to see available languages.</p>
        </div>
      ) : translations.length === 0 ? (
        <div className="text-center py-8 border-2 border-dashed rounded-lg">
          <Globe className="h-12 w-12 mx-auto mb-4 text-muted-foreground opacity-50" />
          <p className="text-sm text-muted-foreground mb-2">No translations added yet.</p>
          <p className="text-xs text-muted-foreground">
            Add translations to make this feed available in multiple languages.
          </p>
          {countryLanguages.length > 0 && (
            <div className="mt-4">
              <p className="text-xs text-muted-foreground mb-2">Available languages:</p>
              <div className="flex flex-wrap gap-2 justify-center">
                {countryLanguages.map((lang: any) => (
                  <Badge key={lang.language_code} variant="outline">
                    {lang.language_name} ({lang.language_code})
                  </Badge>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Language</TableHead>
                <TableHead>Language Code</TableHead>
                <TableHead>Translation</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {translations.map((translation: any, index: number) => (
                <TableRow key={index}>
                  <TableCell>
                    {countryLanguages.find(
                      (l: any) => l.language_code === translation.language_code
                    )?.language_name || translation.language_code}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline">{translation.language_code}</Badge>
                  </TableCell>
                  <TableCell className="font-medium">{translation.translation_text}</TableCell>
                  <TableCell className="text-right">
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={async () => {
                        if (!confirm(`Delete translation for ${translation.language_code}?`)) {
                          return;
                        }
                        if (!feedId || !userEmail) {
                          toast.error('Feed ID or user email missing');
                          return;
                        }
                        try {
                          setIsLoading(true);
                          await countryAdminFeedsApi.deleteTranslation(
                            userEmail,
                            feedId,
                            translation.id
                          );
                          toast.success('Translation deleted successfully');
                          // Refetch translations
                          queryClient.invalidateQueries({ queryKey: ['feed-translations', feedId] });
                        } catch (error: any) {
                          toast.error(error.response?.data?.detail || 'Failed to delete translation');
                        } finally {
                          setIsLoading(false);
                        }
                      }}
                      disabled={isLoading}
                    >
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Add Translation Dialog */}
      <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add Translation</DialogTitle>
            <DialogDescription>
              Add a translation for the feed name: <strong>{feedName}</strong>
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="language">Language</Label>
              <Select value={newLanguage} onValueChange={setNewLanguage}>
                <SelectTrigger>
                  <SelectValue placeholder="Select a language" />
                </SelectTrigger>
                <SelectContent>
                  {countryLanguages
                    .filter((lang: any) => {
                      // Don't show languages that already have translations
                      return !translations.some(
                        (t: any) => t.language_code === lang.language_code
                      );
                    })
                    .map((lang: any) => (
                      <SelectItem key={lang.language_code} value={lang.language_code}>
                        {lang.language_name} ({lang.language_code})
                      </SelectItem>
                    ))}
                </SelectContent>
              </Select>
              {countryLanguages.length === 0 && (
                <p className="text-xs text-muted-foreground">
                  No languages configured for this country. Please configure languages in the
                  country settings.
                </p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="translation">Translation Text</Label>
              <Input
                id="translation"
                value={newTranslation}
                onChange={(e) => setNewTranslation(e.target.value)}
                placeholder={`Enter translation for "${feedName}"`}
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setIsAddDialogOpen(false);
                setNewLanguage('');
                setNewTranslation('');
              }}
              disabled={addTranslationMutation.isPending}
            >
              Cancel
            </Button>
            <Button
              onClick={handleAddTranslation}
              disabled={!newLanguage || !newTranslation.trim() || addTranslationMutation.isPending}
            >
              {addTranslationMutation.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Adding...
                </>
              ) : (
                'Add Translation'
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

