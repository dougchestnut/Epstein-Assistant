'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { db } from '@/lib/firebase';
import { collection, query, where, limit, getDocs, orderBy, startAfter, DocumentData, QueryDocumentSnapshot } from 'firebase/firestore';
import Link from 'next/link';

export default function Home() {
    const [items, setItems] = useState<DocumentData[]>([]);
    const [loading, setLoading] = useState(true);
    const [lastDoc, setLastDoc] = useState<QueryDocumentSnapshot<DocumentData> | null>(null);
    const [filterType, setFilterType] = useState<'document' | 'photo'>('document');
    const [hasMore, setHasMore] = useState(true);
    const observer = useRef<IntersectionObserver | null>(null);

    const lastItemRef = useCallback((node: HTMLDivElement) => {
        if (loading) return;
        if (observer.current) observer.current.disconnect();
        observer.current = new IntersectionObserver(entries => {
            if (entries[0].isIntersecting && hasMore) {
                fetchItems(false);
            }
        });
        if (node) observer.current.observe(node);
    }, [loading, hasMore]);

    const fetchItems = async (isInitial = false) => {
        setLoading(true);
        try {
            // Determine collection based on filter
            const collectionName = filterType === 'document' ? 'documents' : 'images';
            const itemsRef = collection(db, collectionName);

            const constraint = [];

            // Ingested items use ingested_at, fallback if needed
            constraint.push(orderBy('ingested_at', 'desc'));
            constraint.push(limit(20));

            let q = query(itemsRef, ...constraint);

            if (!isInitial && lastDoc) {
                q = query(q, startAfter(lastDoc));
            }

            const snapshot = await getDocs(q);
            const newItems = snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));

            if (isInitial) {
                setItems(newItems);
            } else {
                setItems(prev => [...prev, ...newItems]);
            }

            setLastDoc(snapshot.docs[snapshot.docs.length - 1] || null);
            if (snapshot.docs.length < 20) {
                setHasMore(false);
            }
        } catch (error) {
            console.error("Error fetching items:", error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        setItems([]);
        setLastDoc(null);
        setHasMore(true);
        fetchItems(true);
    }, [filterType]);

    return (
        <div className="min-h-screen bg-gray-50">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">

                {/* Header & Controls */}
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-8 space-y-4 sm:space-y-0">
                    <div>
                        <h1 className="text-3xl font-bold text-gray-900">Epstein Archive</h1>
                        <p className="mt-1 text-sm text-gray-500">
                            Browse collected documents and media
                        </p>
                    </div>

                    <div className="flex space-x-2 bg-white p-1 rounded-lg border border-gray-200 shadow-sm">
                        {(['document', 'photo'] as const).map((type) => (
                            <button
                                key={type}
                                onClick={() => setFilterType(type)}
                                className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${filterType === type
                                    ? 'bg-indigo-600 text-white shadow-sm'
                                    : 'text-gray-600 hover:bg-gray-50'
                                    }`}
                            >
                                {type.charAt(0).toUpperCase() + type.slice(1)}s
                            </button>
                        ))}
                    </div>
                </div>

                {/* Content Grid */}
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-6">
                    {items.map((item, index) => {
                        const isLastElement = items.length === index + 1;
                        const isDoc = filterType === 'document';
                        // Determine route based on type
                        const href = isDoc ? `/documents/${item.id}` : `/images/${item.id}`;
                        // Use preview_medium from new ingest schema
                        const imgSrc = item.preview_medium || item.preview_thumb;

                        return (
                            <div
                                key={item.id}
                                ref={isLastElement ? lastItemRef : null}
                                className="group relative bg-white rounded-xl shadow-sm hover:shadow-md transition-shadow duration-200 overflow-hidden border border-gray-100 flex flex-col"
                            >
                                {/* Thumbnail / Preview */}
                                <div className="aspect-square bg-gray-100 relative overflow-hidden">
                                    {imgSrc ? (
                                        <img
                                            src={imgSrc}
                                            alt={item.title || item.image_name}
                                            loading="lazy"
                                            className="object-cover w-full h-full transform group-hover:scale-105 transition-transform duration-300"
                                        />
                                    ) : (
                                        <div className="flex items-center justify-center h-full text-gray-400">
                                            <span className="text-xs">No Preview</span>
                                        </div>
                                    )}

                                    {/* Overlay Type Badge */}
                                    <div className="absolute top-2 right-2">
                                        <span className={`inline-flex items-center px-2 py-1 rounded-md text-xs font-medium shadow-sm backdrop-blur-md bg-opacity-90 ${isDoc
                                            ? 'bg-green-100/90 text-green-800'
                                            : 'bg-blue-100/90 text-blue-800'
                                            }`}>
                                            {isDoc ? 'DOC' : 'IMG'}
                                        </span>
                                    </div>
                                </div>

                                {/* Card Footer */}
                                <div className="p-3">
                                    <h3 className="text-sm font-medium text-gray-900 truncate" title={item.title || item.image_name}>
                                        {item.title || item.image_name}
                                    </h3>
                                    <p className="mt-1 text-xs text-gray-500 truncate">
                                        {item.ingested_at ? new Date(item.ingested_at.seconds * 1000).toLocaleDateString() : 'Unknown Date'}
                                    </p>
                                </div>

                                {/* Full Card Link */}
                                <Link href={href} className="absolute inset-0 focus:outline-none">
                                    <span className="sr-only">View details</span>
                                </Link>
                            </div>
                        );
                    })}
                </div>

                {/* Loading State */}
                {loading && (
                    <div className="mt-8 flex justify-center">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
                    </div>
                )}

                {/* Empty State */}
                {!loading && items.length === 0 && (
                    <div className="text-center py-20">
                        <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-gray-100 mb-4">
                            <span className="text-2xl">EMPTY</span>
                        </div>
                        <h3 className="text-lg font-medium text-gray-900">No items found</h3>
                        <p className="mt-1 text-gray-500">Try checking back later.</p>
                    </div>
                )}
            </div>
        </div>
    );
}
