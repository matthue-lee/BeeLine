import { StatusBar } from 'expo-status-bar';
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  Modal,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';

const API_BASE_URL = process.env.EXPO_PUBLIC_API_BASE_URL ?? 'http://127.0.0.1:5000';

type ReleaseLink = {
  article_id: string;
  title: string;
  source: string;
  url: string;
  similarity: number;
  rationale?: string | null;
};

type Release = {
  id: string;
  title: string;
  url: string;
  published_at: string | null;
  minister?: string | null;
  portfolio?: string | null;
  categories: string[];
  status: string;
  word_count: number | null;
  text_clean?: string | null;
  links?: ReleaseLink[];
};

type ApiResponse = {
  items: Release[];
};

export default function App(): React.JSX.Element {
  const [data, setData] = useState<Release[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [selected, setSelected] = useState<Release | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchReleases = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/releases?limit=50`);
      if (!response.ok) {
        throw new Error(`Request failed with ${response.status}`);
      }
      const payload = (await response.json()) as ApiResponse;
      setData(payload.items ?? []);
      setError(null);
    } catch (err) {
      console.error('Failed to load releases', err);
      setError('Unable to reach the BeeLine API. Is the Flask server running?');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchReleases();
  }, [fetchReleases]);

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    fetchReleases();
  }, [fetchReleases]);

  const renderItem = useCallback(
    ({ item }: { item: Release }) => (
      <TouchableOpacity style={styles.card} onPress={() => setSelected(item)}>
        <Text style={styles.title}>{item.title}</Text>
        <Text style={styles.meta}>
          {item.published_at ? new Date(item.published_at).toLocaleString() : 'Unknown date'}
        </Text>
        <Text style={styles.meta}>
          {[item.minister, item.portfolio].filter(Boolean).join(' — ') || 'No minister/portfolio'}
        </Text>
        <Text numberOfLines={4} style={styles.preview}>
          {(item.text_clean || '').trim() || 'No cleaned text available yet.'}
        </Text>
        <View style={styles.badgeRow}>
          <View style={styles.badge}>
            <Text style={styles.badgeText}>{item.status}</Text>
          </View>
          {item.word_count ? (
            <View style={styles.badge}>
              <Text style={styles.badgeText}>{item.word_count} words</Text>
            </View>
          ) : null}
        </View>
        {item.links && item.links.length ? (
          <View style={styles.linksContainer}>
            {item.links.map((link) => (
              <Text key={`${item.id}-${link.article_id}`} style={styles.linkText} numberOfLines={2}>
                {link.source}: {link.title}
              </Text>
            ))}
          </View>
        ) : null}
      </TouchableOpacity>
    ),
    [],
  );

  const keyExtractor = useCallback((item: Release) => item.id, []);

  const header = useMemo(
    () => (
      <View style={styles.header}>
        <Text style={styles.headerTitle}>BeeLine Releases</Text>
        <Text style={styles.headerSubtitle}>{API_BASE_URL}</Text>
      </View>
    ),
    [],
  );

  if (loading) {
    return (
      <SafeAreaProvider>
        <SafeAreaView style={styles.container} edges={['top', 'left', 'right']}>
          <ActivityIndicator size="large" />
          <Text style={styles.meta}>Loading releases…</Text>
        </SafeAreaView>
      </SafeAreaProvider>
    );
  }

  return (
    <SafeAreaProvider>
      <SafeAreaView style={styles.container} edges={['top', 'left', 'right']}>
        {error ? <Text style={styles.error}>{error}</Text> : null}
        <FlatList
          data={data}
          keyExtractor={keyExtractor}
          renderItem={renderItem}
          ListHeaderComponent={header}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
          contentContainerStyle={styles.listContent}
        />
        <StatusBar style="auto" />
      </SafeAreaView>
      <Modal visible={!!selected} animationType="slide" onRequestClose={() => setSelected(null)}>
        <SafeAreaProvider>
          <SafeAreaView style={styles.modalContainer} edges={['top', 'left', 'right', 'bottom']}>
            <TouchableOpacity onPress={() => setSelected(null)} style={styles.closeButton}>
              <Text style={styles.closeButtonText}>Close</Text>
            </TouchableOpacity>
            {selected ? (
              <ScrollView style={styles.modalContent}>
                <Text style={styles.title}>{selected.title}</Text>
                <Text style={styles.meta}>
                  {selected.published_at ? new Date(selected.published_at).toLocaleString() : 'Unknown date'}
                </Text>
                <Text style={styles.meta}>{selected.url}</Text>
                <Text style={styles.modalBody}>{selected.text_clean || 'No cleaned text yet.'}</Text>
              </ScrollView>
            ) : null}
          </SafeAreaView>
        </SafeAreaProvider>
      </Modal>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f6f7fb',
  },
  listContent: {
    padding: 16,
    gap: 12,
  },
  header: {
    paddingBottom: 12,
  },
  headerTitle: {
    fontSize: 24,
    fontWeight: '700',
  },
  headerSubtitle: {
    fontSize: 12,
    color: '#687076',
  },
  card: {
    padding: 16,
    borderRadius: 12,
    backgroundColor: '#fff',
    shadowColor: '#000',
    shadowOpacity: 0.05,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 2 },
    elevation: 1,
  },
  title: {
    fontSize: 18,
    fontWeight: '600',
    marginBottom: 4,
  },
  meta: {
    fontSize: 12,
    color: '#687076',
  },
  preview: {
    marginTop: 8,
    fontSize: 14,
    color: '#11181c',
  },
  badgeRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginTop: 12,
  },
  badge: {
    borderRadius: 999,
    backgroundColor: '#eef0f5',
    paddingHorizontal: 12,
    paddingVertical: 4,
  },
  badgeText: {
    fontSize: 12,
    color: '#687076',
  },
  linksContainer: {
    marginTop: 12,
    gap: 4,
  },
  linkText: {
    fontSize: 12,
    color: '#0f172a',
  },
  error: {
    color: '#b42318',
    padding: 16,
    textAlign: 'center',
  },
  modalContainer: {
    flex: 1,
    backgroundColor: '#fff',
  },
  closeButton: {
    alignSelf: 'flex-end',
    padding: 16,
  },
  closeButtonText: {
    color: '#006adc',
    fontWeight: '600',
  },
  modalContent: {
    paddingHorizontal: 16,
  },
  modalBody: {
    fontSize: 15,
    lineHeight: 22,
    marginTop: 12,
    color: '#11181c',
  },
});
