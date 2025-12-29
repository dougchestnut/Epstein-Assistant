"use client";

import { useEffect, useState } from "react";
import { doc, getDoc, DocumentData } from "firebase/firestore";
import { db } from "@/lib/firebase";
import { useParams } from "next/navigation";
import Link from "next/link";

export default function ImageDetail() {
    const { id } = useParams();
    const [item, setItem] = useState<DocumentData | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        if (!id) return;
        const fetchItem = async () => {
            try {
                const docRef = doc(db, "items", id as string);
                const docSnap = await getDoc(docRef);
                if (docSnap.exists()) {
                    setItem(docSnap.data());
                } else {
                    console.log("No such document!");
                }
            } catch (err) {
                console.error("Error getting document:", err);
            }
            setLoading(false);
        };
        fetchItem();
    }, [id]);

    if (loading) return (
        <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
            <div className="w-8 h-8 border-4 border-zinc-700 border-t-emerald-500 rounded-full animate-spin"></div>
        </div>
    );

    if (!item) return (
        <div className="min-h-screen bg-zinc-950 flex flex-col items-center justify-center text-zinc-400">
            <p className="mb-4">Document not found.</p>
            <Link href="/" className="text-emerald-400 hover:text-emerald-300 underline">Back to Browse</Link>
        </div>
    );

    return (
        <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col">
            <nav className="p-4 border-b border-zinc-900 bg-zinc-950/50 backdrop-blur fixed top-0 w-full z-10 flex items-center justify-between">
                <Link href="/" className="flex items-center gap-2 text-zinc-400 hover:text-white transition-colors">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m15 18-6-6 6-6" /></svg>
                    Back to Archive
                </Link>
                <h1 className="text-sm font-medium text-zinc-500 truncate max-w-md">{item.title}</h1>
                <div className="w-20"></div> {/* Spacer for center alignment */}
            </nav>

            <main className="flex-1 flex flex-col lg:flex-row h-full pt-16">
                {/* Image Viewer */}
                <div className="flex-1 bg-black flex items-center justify-center p-4 lg:p-10 relative group">
                    {/* Background blur effect */}
                    <div className="absolute inset-0 overflow-hidden opacity-20 pointer-events-none">
                        <img
                            src={item.medium_url || item.thumbnail_url}
                            className="w-full h-full object-cover blur-3xl scale-110"
                            aria-hidden="true"
                        />
                    </div>

                    <img
                        src={item.medium_url || item.thumbnail_url || item.storage_url}
                        alt={item.title}
                        className="max-h-[85vh] max-w-full object-contain shadow-2xl relative z-10 rounded-sm"
                    />

                    <div className="absolute bottom-6 left-1/2 -translate-x-1/2 flex items-center gap-4 opacity-0 group-hover:opacity-100 transition-opacity">
                        {item.original_url && (
                            <a
                                href={item.original_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="bg-white/10 hover:bg-white/20 backdrop-blur text-white px-4 py-2 rounded-full text-sm font-medium transition-colors border border-white/10"
                            >
                                View Original Source
                            </a>
                        )}
                    </div>
                </div>

                {/* Sidebar Metadata */}
                <div className="w-full lg:w-96 border-l border-zinc-900 bg-zinc-950 p-6 overflow-y-auto max-h-[calc(100vh-4rem)]">
                    <h2 className="text-2xl font-bold mb-6 text-emerald-500 break-words">{item.title}</h2>

                    <div className="space-y-6">
                        <div>
                            <h3 className="text-xs uppercase tracking-wider text-zinc-600 mb-2">Original Source</h3>
                            <a href={item.original_url} target="_blank" className="text-blue-400 hover:underline break-all text-sm block">
                                {item.original_url}
                            </a>
                        </div>

                        {item.metadata && (
                            <div>
                                <h3 className="text-xs uppercase tracking-wider text-zinc-600 mb-2">Metadata</h3>
                                <pre className="text-xs bg-zinc-900 p-4 rounded-lg overflow-x-auto text-zinc-400 font-mono">
                                    {JSON.stringify(item.metadata, null, 2)}
                                </pre>
                            </div>
                        )}

                        <div className="pt-6 border-t border-zinc-900">
                            <p className="text-xs text-zinc-600">ID: <span className="font-mono text-zinc-500">{id}</span></p>
                        </div>
                    </div>
                </div>
            </main>
        </div>
    );
}
