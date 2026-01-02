"use client";

import { useEffect, useState } from "react";
import { doc, getDoc, collection, query, where, getDocs, orderBy, DocumentData } from "firebase/firestore";
import { db } from "@/lib/firebase";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import TextViewer from "@/components/TextViewer";

export default function DocumentDetail() {
    const { id } = useParams();
    const router = useRouter();
    const [docItem, setDocItem] = useState<DocumentData | null>(null);
    const [childImages, setChildImages] = useState<DocumentData[]>([]);
    const [loading, setLoading] = useState(true);
    const [activeTab, setActiveTab] = useState<'content' | 'ocr'>('content');

    useEffect(() => {
        if (!id) return;
        const fetchData = async () => {
            try {
                // Fetch Document
                const docRef = doc(db, "documents", id as string);
                const docSnap = await getDoc(docRef);

                if (docSnap.exists()) {
                    setDocItem(docSnap.data());

                    // Fetch Child Images
                    const imagesRef = collection(db, "images");
                    const q = query(
                        imagesRef,
                        where("parent_doc_id", "==", id),
                        orderBy("page_num", "asc")
                    );

                    const querySnapshot = await getDocs(q);
                    const images = querySnapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));
                    setChildImages(images);
                }
            } catch (err) {
                console.error("Error fetching data:", err);
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, [id]);

    if (loading) return (
        <div className="min-h-screen bg-gray-50 flex items-center justify-center">
            <div className="w-8 h-8 border-4 border-gray-300 border-t-indigo-600 rounded-full animate-spin"></div>
        </div>
    );

    if (!docItem) return (
        <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center text-gray-500">
            <p className="mb-4">Document not found.</p>
            <button onClick={() => router.back()} className="text-indigo-600 hover:underline">Go Back</button>
        </div>
    );

    // Prepare content URLs
    const contentUrl = docItem.content?.markdown_url || docItem.content?.text_url;
    const contentIsMd = !!docItem.content?.markdown_url;

    const ocrUrl = docItem.ocr?.markdown_url || docItem.ocr?.text_url;
    const ocrIsMd = !!docItem.ocr?.markdown_url;

    const hasContent = !!contentUrl;
    const hasOcr = !!ocrUrl;

    return (
        <div className="min-h-screen bg-gray-50">
            {/* Nav */}
            <nav className="bg-white border-b border-gray-200 px-4 py-4 sm:px-6 lg:px-8 flex items-center justify-between sticky top-0 z-10">
                <button
                    onClick={() => router.back()}
                    className="flex items-center text-sm font-medium text-gray-500 hover:text-gray-900 transition-colors"
                >
                    <span className="mr-2">←</span> Back
                </button>
                <h1 className="text-lg font-bold text-gray-900 truncate max-w-xl">{docItem.title}</h1>
                <div className="w-16"></div>
            </nav>

            <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">

                    {/* Left: Document Information & Preview */}
                    <div className="lg:col-span-1 space-y-6">
                        <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
                            <div className="aspect-[3/4] bg-gray-100 relative">
                                <img
                                    src={docItem.preview_medium || docItem.preview_thumb}
                                    alt={docItem.title}
                                    className="w-full h-full object-cover"
                                />
                            </div>
                            <div className="p-4 space-y-4">
                                <a
                                    href={docItem.url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="block w-full text-center bg-indigo-600 hover:bg-indigo-700 text-white font-medium py-2 px-4 rounded-lg transition-colors"
                                >
                                    Open PDF
                                </a>
                                {docItem.source_page && (
                                    <a
                                        href={docItem.source_page}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="block w-full text-center bg-white border border-gray-300 text-gray-700 hover:bg-gray-50 font-medium py-2 px-4 rounded-lg transition-colors"
                                    >
                                        View Source Page
                                    </a>
                                )}
                            </div>
                        </div>

                        {/* Metadata Block */}
                        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-4">
                            <h3 className="text-sm font-semibold text-gray-900 mb-2">Details</h3>
                            <div className="space-y-2 text-sm text-gray-600">
                                <p><span className="text-gray-400">Filename:</span> <span className="font-mono break-all">{docItem.filename}</span></p>
                                <p><span className="text-gray-400">Ingested:</span> {docItem.ingested_at ? new Date(docItem.ingested_at.seconds * 1000).toLocaleDateString() : 'N/A'}</p>

                                {/* Info JSON Data */}
                                {docItem.info && (
                                    <div className="mt-4 pt-4 border-t border-gray-100">
                                        <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Metadata</h4>
                                        <dl className="grid grid-cols-1 gap-x-4 gap-y-2">
                                            {Object.entries(docItem.info).map(([key, value]) => {
                                                if (typeof value === 'object') return null; // Skip nested for now
                                                return (
                                                    <div key={key} className="sm:col-span-1">
                                                        <dt className="text-xs text-gray-400 capitalize">{key.replace(/_/g, ' ')}</dt>
                                                        <dd className="text-xs font-medium text-gray-900 break-words">{String(value)}</dd>
                                                    </div>
                                                )
                                            })}
                                        </dl>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>

                    {/* Right: Content & Images */}
                    <div className="lg:col-span-2 space-y-8">

                        {/* 1. Text Content Viewer (Tabs) */}
                        {(hasContent || hasOcr) && (
                            <section>
                                <div className="border-b border-gray-200 mb-4">
                                    <nav className="-mb-px flex space-x-8">
                                        {hasContent && (
                                            <button
                                                onClick={() => setActiveTab('content')}
                                                className={`whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm transition-colors ${activeTab === 'content'
                                                    ? 'border-indigo-500 text-indigo-600'
                                                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                                                    }`}
                                            >
                                                Extracted Content
                                            </button>
                                        )}
                                        {hasOcr && (
                                            <button
                                                onClick={() => setActiveTab('ocr')}
                                                className={`whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm transition-colors ${activeTab === 'ocr'
                                                    ? 'border-indigo-500 text-indigo-600'
                                                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                                                    }`}
                                            >
                                                OCR Text
                                            </button>
                                        )}
                                    </nav>
                                </div>

                                <div className="min-h-[200px] max-h-[500px] overflow-y-auto rounded-lg border border-gray-100 bg-white">
                                    {(activeTab === 'content' && hasContent) && (
                                        <TextViewer url={contentUrl} isMarkdown={contentIsMd} className="border-0 shadow-none" />
                                    )}
                                    {(activeTab === 'ocr' && hasOcr) && (
                                        <TextViewer url={ocrUrl} isMarkdown={ocrIsMd} className="border-0 shadow-none" />
                                    )}
                                </div>
                            </section>
                        )}


                        {/* 2. Extracted Photos Gallery */}
                        <section>
                            <h2 className="text-xl font-bold text-gray-900 mb-6 flex items-center">
                                Extracted Photos
                                <span className="ml-2 bg-indigo-100 text-indigo-800 text-xs font-semibold px-2.5 py-0.5 rounded-full">
                                    {childImages.length}
                                </span>
                            </h2>

                            {childImages.length > 0 ? (
                                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-3 gap-4">
                                    {childImages.map((img) => (
                                        <Link key={img.id} href={`/images/${img.id}`} className="group relative aspect-square bg-gray-100 rounded-lg overflow-hidden block shadow-sm hover:shadow-md transition-all">
                                            <img
                                                src={img.preview_medium || img.preview_thumb}
                                                loading="lazy"
                                                alt={img.image_name}
                                                className="w-full h-full object-cover transform group-hover:scale-105 transition-transform duration-300"
                                            />
                                            <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors"></div>
                                            <div className="absolute bottom-2 left-2 bg-black/50 backdrop-blur text-white text-[10px] px-1.5 py-0.5 rounded">
                                                Page {img.page_num}
                                            </div>
                                        </Link>
                                    ))}
                                </div>
                            ) : (
                                <div className="bg-gray-50 rounded-xl border border-dashed border-gray-300 p-12 text-center">
                                    <p className="text-gray-500">No photos extracted from this document.</p>
                                </div>
                            )}
                        </section>
                    </div>
                </div>
            </main>
        </div>
    );
}
