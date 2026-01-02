"use client";

import { useEffect, useState } from "react";
import { doc, getDoc, DocumentData } from "firebase/firestore";
import { db } from "@/lib/firebase";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import TextViewer from "@/components/TextViewer";

export default function ImageDetail() {
    const { id } = useParams();
    const router = useRouter();
    const [item, setItem] = useState<DocumentData | null>(null);
    const [parentDoc, setParentDoc] = useState<DocumentData | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        if (!id) return;
        const fetchItem = async () => {
            try {
                // Fetch Image
                const docRef = doc(db, "images", id as string);
                const docSnap = await getDoc(docRef);

                if (docSnap.exists()) {
                    const data = docSnap.data();
                    setItem(data);

                    // Fetch Parent Document if ID exists
                    if (data.parent_doc_id) {
                        try {
                            const parentRef = doc(db, "documents", data.parent_doc_id);
                            const parentSnap = await getDoc(parentRef);
                            if (parentSnap.exists()) {
                                setParentDoc({ id: parentSnap.id, ...parentSnap.data() });
                            }
                        } catch (e) {
                            console.error("Error fetching parent doc:", e);
                        }
                    }
                }
            } catch (err) {
                console.error("Error getting document:", err);
            } finally {
                setLoading(false);
            }
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
            <p className="mb-4">Image not found.</p>
            <button onClick={() => router.back()} className="text-emerald-400 hover:text-emerald-300 underline">Go Back</button>
        </div>
    );

    const ocrUrl = item.ocr?.markdown_url || item.ocr?.text_url;
    const ocrIsMd = !!item.ocr?.markdown_url;

    return (
        <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col">
            {/* Header */}
            <nav className="p-4 border-b border-zinc-900 bg-zinc-950/50 backdrop-blur fixed top-0 w-full z-10 flex items-center justify-between">
                <button onClick={() => router.back()} className="flex items-center gap-2 text-zinc-400 hover:text-white transition-colors text-sm">
                    <span>←</span> Back
                </button>
                <div className="flex-1"></div>
                {/* Parent Link in Header (Optional, but we have big one in sidebar) */}
            </nav>

            <main className="flex-1 flex flex-col lg:flex-row h-full pt-16">
                {/* Main Image Viewer */}
                <div className="flex-1 bg-black flex items-center justify-center p-4 lg:p-10 relative group overflow-hidden">
                    {/* Background Ambient Blur */}
                    <div className="absolute inset-0 overflow-hidden opacity-20 pointer-events-none">
                        <img
                            src={item.preview_medium || item.preview_thumb}
                            className="w-full h-full object-cover blur-3xl scale-150"
                            aria-hidden="true"
                        />
                    </div>

                    <img
                        src={item.preview_medium || item.preview_thumb}
                        alt={item.image_name}
                        className="max-h-[85vh] max-w-full object-contain shadow-2xl relative z-10 rounded-sm"
                    />
                </div>

                {/* Sidebar Info */}
                <div className="w-full lg:w-96 border-l border-zinc-900 bg-zinc-950 p-6 overflow-y-auto max-h-[calc(100vh-4rem)]">

                    {/* Parent Document Link Card */}
                    {parentDoc && (
                        <div className="mb-8 p-4 rounded-lg bg-zinc-900/50 border border-zinc-800 hover:border-emerald-500/50 transition-colors group">
                            <h3 className="text-xs uppercase tracking-wider text-zinc-500 mb-3 font-semibold">From Document</h3>
                            <Link href={`/documents/${parentDoc.id}`} className="flex gap-4 items-start">
                                <div className="w-16 h-20 bg-zinc-800 shrink-0 rounded overflow-hidden relative">
                                    {parentDoc.preview_thumb ? (
                                        <img src={parentDoc.preview_thumb} alt="" className="w-full h-full object-cover" />
                                    ) : (
                                        <div className="w-full h-full flex items-center justify-center text-zinc-600 font-bold text-xs">PDF</div>
                                    )}
                                </div>
                                <div>
                                    <p className="text-sm font-medium text-emerald-400 group-hover:underline line-clamp-2">
                                        {parentDoc.title || "Untitled Document"}
                                    </p>
                                    <p className="text-xs text-zinc-500 mt-1">Page {item.page_num}</p>
                                </div>
                            </Link>
                        </div>
                    )}

                    <h2 className="text-xl font-bold mb-6 text-zinc-200 break-words">{item.image_name}</h2>

                    <div className="space-y-8">
                        {/* Analysis Data (New) */}
                        {item.analysis && (
                            <div className="p-4 bg-zinc-900/40 rounded border border-zinc-800 space-y-4">
                                <h3 className="text-xs uppercase tracking-wider text-emerald-500 font-bold mb-2">AI Analysis</h3>

                                {item.analysis.visual_description && (
                                    <div>
                                        <h4 className="text-xs text-zinc-500 mb-1">Visual Description</h4>
                                        <p className="text-sm text-zinc-300 leading-relaxed">{item.analysis.visual_description}</p>
                                    </div>
                                )}

                                {item.analysis.keywords && item.analysis.keywords.length > 0 && (
                                    <div>
                                        <h4 className="text-xs text-zinc-500 mb-1">Keywords</h4>
                                        <div className="flex flex-wrap gap-2">
                                            {item.analysis.keywords.map((kw: string) => (
                                                <span key={kw} className="bg-zinc-800 text-zinc-300 text-xs px-2 py-1 rounded">
                                                    {kw}
                                                </span>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}

                        {/* OCR Text Viewer (New) */}
                        {ocrUrl && (
                            <div>
                                <h3 className="text-xs uppercase tracking-wider text-zinc-600 mb-2">Extracted Text</h3>
                                <div className="max-h-60 overflow-y-auto rounded bg-zinc-900 border border-zinc-800 text-left">
                                    <TextViewer
                                        url={ocrUrl}
                                        isMarkdown={ocrIsMd}
                                        className="border-0 bg-transparent text-zinc-300 !p-3"
                                    />
                                </div>
                            </div>
                        )}

                        <div>
                            <h3 className="text-xs uppercase tracking-wider text-zinc-600 mb-2">Original Context</h3>
                            <a href={item.unique_uri} target="_blank" className="text-blue-400 hover:underline break-all text-xs block">
                                {item.unique_uri}
                            </a>
                        </div>

                        {item.eval && (
                            <div>
                                <h3 className="text-xs uppercase tracking-wider text-zinc-600 mb-2">Evaluation</h3>
                                <div className="flex gap-2 flex-wrap">
                                    {item.eval.is_likely_photo && (
                                        <span className="bg-emerald-900/30 text-emerald-400 text-xs px-2 py-1 rounded">Photo</span>
                                    )}
                                    {item.eval.is_screenshot && (
                                        <span className="bg-blue-900/30 text-blue-400 text-xs px-2 py-1 rounded">Screenshot</span>
                                    )}
                                </div>
                            </div>
                        )}

                        <div className="pt-6 border-t border-zinc-900">
                            <p className="text-xs text-zinc-600">ID: <span className="font-mono text-zinc-700">{id}</span></p>
                        </div>
                    </div>
                </div>
            </main>
        </div>
    );
}
