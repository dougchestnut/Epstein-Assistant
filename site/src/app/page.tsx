"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { collection, query, limit, getDocs, startAfter, orderBy, where, DocumentData, QueryDocumentSnapshot } from "firebase/firestore";
import { db } from "@/lib/firebase"; // Ensure this matches your export
import Link from "next/link";
import Image from "next/image"; // Note: Next.js Image component might need configuration for external domains

export default function Home() {
    const [items, setItems] = useState<DocumentData[]>([]);
    const [lastDoc, setLastDoc] = useState<QueryDocumentSnapshot<DocumentData> | null>(null);
    const [loading, setLoading] = useState(true);
    const [hasMore, setHasMore] = useState(true);
    const observer = useRef<IntersectionObserver | null>(null);

    const lastElementRef = useCallback((node: HTMLAnchorElement | null) => {
        if (loading) return;
        if (observer.current) observer.current.disconnect();
        observer.current = new IntersectionObserver(entries => {
            if (entries[0].isIntersecting && hasMore) {
                loadMore();
            }
        });
        if (node) observer.current.observe(node);
    }, [loading, hasMore]);

    const loadInitial = async () => {
        setLoading(true);
        try {
            console.log("Fetching items...");
            // Filter: needs_ocr == false AND is_empty == false
            // This requires a composite index: analysis.needs_ocr ASC, analysis.is_empty ASC, created_at DESC
            const q = query(
                collection(db, "items"),
                where("analysis.needs_ocr", "==", false),
                where("analysis.is_empty", "==", false),
                orderBy("created_at", "desc"),
                limit(20)
            );
            const snapshot = await getDocs(q);
            console.log(`Found ${snapshot.docs.length} items`);

            const newItems = snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));
            setItems(newItems);

            if (snapshot.docs.length > 0) {
                setLastDoc(snapshot.docs[snapshot.docs.length - 1]);
            }
            setHasMore(snapshot.docs.length === 20);
        } catch (err) {
            console.error("Error loading items details:", err);
            // @ts-ignore
            if (err.code === 'failed-precondition') {
                console.error("Index missing? Check console link.");
            }
        }
        setLoading(false);
    };

    const loadMore = async () => {
        if (!lastDoc) return;
        setLoading(true);
        try {
            const q = query(
                collection(db, "items"),
                where("analysis.needs_ocr", "==", false),
                where("analysis.is_empty", "==", false),
                orderBy("created_at", "desc"),
                startAfter(lastDoc),
                limit(20)
            );
            const snapshot = await getDocs(q);
            if (!snapshot.empty) {
                const newItems = snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));
                setItems(prev => [...prev, ...newItems]);
                setLastDoc(snapshot.docs[snapshot.docs.length - 1]);
                setHasMore(snapshot.docs.length === 20);
            } else {
                setHasMore(false);
            }
        } catch (err) {
            console.error("Error loading more:", err);
        }
        setLoading(false);
    };

    useEffect(() => {
        loadInitial();
    }, []);

    return (
        <main className="min-h-screen p-8 bg-zinc-950 text-zinc-100">
            <header className="mb-12 text-center">
                <h1 className="text-4xl font-bold tracking-tight mb-2 bg-gradient-to-r from-blue-400 to-emerald-400 bg-clip-text text-transparent">
                    Epstein Documents
                </h1>
                <p className="text-zinc-500">Archive Browser</p>
            </header>

            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6 max-w-7xl mx-auto">
                {items.map((item, index) => {
                    // Use thumb url or fallback
                    const imgSrc = item.thumbnail_url || item.storage_url || "/placeholder.jpg";
                    // Note: external images need hostname configured in next.config.ts or use regular img tag
                    return (
                        <Link
                            key={item.id}
                            href={`/image/${item.id}`}
                            ref={index === items.length - 1 ? lastElementRef : null}
                            className="group relative aspect-[3/4] overflow-hidden rounded-xl bg-zinc-900 border border-zinc-800 transition-all hover:scale-[1.02] hover:shadow-2xl hover:shadow-blue-900/20"
                        >
                            {/* Fallback to simple img tag to avoid Next.js domain config issues for now, or use unoptimized */}
                            <img
                                src={imgSrc}
                                alt={item.title || "Document"}
                                className="object-cover w-full h-full opacity-80 group-hover:opacity-100 transition-opacity duration-500"
                                loading="lazy"
                            />
                            <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300 flex flex-col justify-end p-4">
                                <h3 className="text-sm font-medium text-white truncate">{item.title}</h3>
                            </div>
                        </Link>
                    );
                })}
            </div>

            {loading && (
                <div className="text-center py-12">
                    <div className="inline-block w-8 h-8 create-spin rounded-full border-4 border-zinc-700 border-t-emerald-500 animate-spin"></div>
                </div>
            )}

            {!hasMore && !loading && (
                <div className="text-center py-12 text-zinc-500">
                    You've reached the end of the archive.
                </div>
            )}
        </main>
    );
}
