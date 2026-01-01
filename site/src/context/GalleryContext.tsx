'use client';

import { createContext, useContext, useState, ReactNode, useEffect, useRef } from 'react';
import { db } from '@/lib/firebase';
import { collection, query, where, limit, getDocs, orderBy, startAfter, DocumentData, QueryDocumentSnapshot } from 'firebase/firestore';

interface GalleryContextType {
    items: DocumentData[];
    loading: boolean;
    filterType: 'document' | 'photo';
    hasMore: boolean;
    setFilterType: (type: 'document' | 'photo') => void;
    fetchMore: () => Promise<void>;
    resetGallery: () => void;
}

const GalleryContext = createContext<GalleryContextType | undefined>(undefined);

export function GalleryProvider({ children }: { children: ReactNode }) {
    const [items, setItems] = useState<DocumentData[]>([]);
    const [loading, setLoading] = useState(true); // Initial load state
    const [lastDoc, setLastDoc] = useState<QueryDocumentSnapshot<DocumentData> | null>(null);
    const [filterType, setFilterType] = useState<'document' | 'photo'>('document');
    const [hasMore, setHasMore] = useState(true);

    // Track if we have initialized the very first fetch to avoid double-fetching on mount
    const initialized = useRef(false);

    const fetchItems = async (isReset = false) => {
        if (!isReset && !hasMore) return;

        // If it's a reset, set loading true. If it's pagination, we might not want global loading, 
        // but for now let's keep it simple.
        if (isReset) setLoading(true);

        try {
            const collectionName = filterType === 'document' ? 'documents' : 'images';
            const itemsRef = collection(db, collectionName);

            const constraint = [];

            // Sort by ingestion time
            constraint.push(orderBy('ingested_at', 'desc'));
            constraint.push(limit(20));

            let q = query(itemsRef, ...constraint);

            if (!isReset && lastDoc) {
                q = query(q, startAfter(lastDoc));
            }

            const snapshot = await getDocs(q);
            const newItems = snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));

            if (isReset) {
                setItems(newItems);
            } else {
                setItems(prev => [...prev, ...newItems]);
            }

            const lastVisible = snapshot.docs[snapshot.docs.length - 1] || null;
            setLastDoc(lastVisible);

            if (snapshot.docs.length < 20) {
                setHasMore(false);
            }
        } catch (error) {
            console.error("Error fetching gallery items:", error);
        } finally {
            setLoading(false);
        }
    };

    // Initial Fetch (only runs once per mount of Provider, which is App-level)
    useEffect(() => {
        if (!initialized.current) {
            initialized.current = true;
            fetchItems(true);
        }
    }, []);

    // Refetch when filter changes
    const handleSetFilterType = (type: 'document' | 'photo') => {
        if (type === filterType) return;
        setFilterType(type);
        setItems([]);
        setLastDoc(null);
        setHasMore(true);
        // We need to trigger the fetch with the new type. 
        // State updates are async, so we can't just call fetchItems(true) immediately with old state.
        // We'll rely on a separate useEffect to watch filterType changes? 
        // Or essentially reset state and let an effect trigger.
        // Better: Reset state here, and have an effect watch `filterType`.
    };

    useEffect(() => {
        // Skip the very first run because the init ref handles it? 
        // Or actually, let's just make `fetchItems` depend on filterType in a clean way.
        // If we just changed filter, we need to reset.
        if (initialized.current) {
            // Reset logic manually before fetch
            setItems([]);
            setLastDoc(null);
            setHasMore(true);

            // We need to wrap fetch in a timeout or pure function to use the NEW filterType 
            // because closure might capture old one? No, useEffect dependency handles it.
            // But we need to separate "Initial Mount" from "Filter Change".
        }
    }, [filterType]);

    // Actually, simplifying: 
    // Just allow fetchItems to read current state? No, closures.
    // Let's use a Ref for filterType if we need it inside non-effect functions?
    // Standard approach: Use Effect for data fetching.

    useEffect(() => {
        // This effect handles both initial load AND filter changes.
        // We just need to handle the "Reset" case properly.

        // We can't easily distinguish "Initial" from "Filter Change" without refs, 
        // but actually we WANT to fetch on filter change.
        // We just need to be careful not to fetch twice on init.

        const load = async () => {
            setLoading(true);
            try {
                // Logic duplicated but safer for Effect
                const collectionName = filterType === 'document' ? 'documents' : 'images';
                const itemsRef = collection(db, collectionName);
                const q = query(itemsRef, orderBy('ingested_at', 'desc'), limit(20));

                const snapshot = await getDocs(q);
                const newItems = snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));

                setItems(newItems);
                setLastDoc(snapshot.docs[snapshot.docs.length - 1] || null);
                setHasMore(snapshot.docs.length >= 20);
            } catch (e) {
                console.error(e);
            } finally {
                setLoading(false);
            }
        };

        load();
    }, [filterType]);

    const fetchMore = async () => {
        if (loading || !hasMore || !lastDoc) return;

        // Pagination doesn't need to enable global 'loading' spinner necessarily, 
        // but helps prevents double-clicks.
        // checking `loading` prevents concurrent fetches.
        // But we probably want a "fetching more" state separate from "full reload".
        // For simplicity, we reuse loading but maybe don't clear items.

        try {
            const collectionName = filterType === 'document' ? 'documents' : 'images';
            const itemsRef = collection(db, collectionName);
            const q = query(
                itemsRef,
                orderBy('ingested_at', 'desc'),
                startAfter(lastDoc),
                limit(20)
            );

            const snapshot = await getDocs(q);
            const newItems = snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));

            if (newItems.length > 0) {
                setItems(prev => [...prev, ...newItems]);
                setLastDoc(snapshot.docs[snapshot.docs.length - 1]);
                setHasMore(snapshot.docs.length >= 20);
            } else {
                setHasMore(false);
            }
        } catch (e) {
            console.error(e);
        }
    };

    const resetGallery = () => {
        // Optional manual reset
    };

    return (
        <GalleryContext.Provider value={{
            items,
            loading,
            filterType,
            hasMore,
            setFilterType,
            fetchMore,
            resetGallery
        }}>
            {children}
        </GalleryContext.Provider>
    );
}

export function useGalleryContext() {
    const context = useContext(GalleryContext);
    if (!context) {
        throw new Error('useGalleryContext must be used within a GalleryProvider');
    }
    return context;
}
