'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { db } from '@/lib/firebase';
import { collection, query, where, limit, getDocs, orderBy, startAfter, DocumentData, QueryDocumentSnapshot } from 'firebase/firestore';
import Link from 'next/link';

export default function Home() {
    const [items, setItems] = useState<DocumentData[]>([]);
    const [loading, setLoading] = useState(true);
    const [lastDoc, setLastDoc] = useState<QueryDocumentSnapshot<DocumentData> | null>(null);
    const [filterType, setFilterType] = useState<'all' | 'document' | 'photo'>('photo');
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
            const itemsRef = collection(db, 'items');
            let q;

            const constraint = [];

            if (filterType === 'document') {
                constraint.push(where('type', '==', 'document'));
            } else if (filterType === 'photo') {
                constraint.push(where('type', '==', 'image'));
                constraint.push(where('is_likely_photo', '==', true));
            }

            constraint.push(orderBy('created_at', 'desc'));
            constraint.push(limit(20));

            q = query(itemsRef, ...constraint);

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
                        {(['photo', 'document', 'all'] as const).map((type) => (
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
                        return (
                            <div
                                key={item.id}
                                ref={isLastElement ? lastItemRef : null}
                                className="group relative bg-white rounded-xl shadow-sm hover:shadow-md transition-shadow duration-200 overflow-hidden border border-gray-100 flex flex-col"
                            >
                                {/* Thumbnail / Preview */}
                                <div className="aspect-square bg-gray-100 relative overflow-hidden">
                                    {item.type === 'image' ? (
                                        <img
                                            src={item.medium_url || item.thumbnail_url}
                                            alt={item.title}
                                            loading="lazy"
                                            className="object-cover w-full h-full transform group-hover:scale-105 transition-transform duration-300"
                                        />
                                    ) : (
                                        <div className="flex items-center justify-center h-full text-gray-400">
                                            <svg className="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                            </svg>
                                        </div>
                                    )}

                                    {/* Overlay Type Badge */}
                                    <div className="absolute top-2 right-2">
                                        <span className={`inline-flex items-center px-2 py-1 rounded-md text-xs font-medium shadow-sm backdrop-blur-md bg-opacity-90 ${item.type === 'document'
                                                ? 'bg-green-100/90 text-green-800'
                                                : 'bg-blue-100/90 text-blue-800'
                                            }`}>
                                            {item.type === 'document' ? 'DOC' : 'IMG'}
                                        </span>
                                    </div>
                                </div>

                                {/* Card Footer */}
                                <div className="p-3">
                                    <h3 className="text-sm font-medium text-gray-900 truncate" title={item.title}>
                                        {item.title}
                                    </h3>
                                    <p className="mt-1 text-xs text-gray-500 truncate">
                                        {new Date(item.created_at?.seconds * 1000).toLocaleDateString()}
                                    </p>
                                </div>

                                {/* Full Card Link */}
                                <Link href={`/item/${item.id}`} className="absolute inset-0 focus:outline-none">
                                    <span className="sr-only">View details for {item.title}</span>
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
                            <svg className="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                            </svg>
                        </div>
                        <h3 className="text-lg font-medium text-gray-900">No items found</h3>
                        <p className="mt-1 text-gray-500">Try adjusting your filters or checking back later.</p>
                    </div>
                )}
            </div>
        </div>
    );
}
