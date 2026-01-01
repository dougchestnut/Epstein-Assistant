"use client";

import { useEffect, useState } from "react";
import { doc, getDoc, collection, query, where, getDocs, orderBy, DocumentData } from "firebase/firestore";
import { db } from "@/lib/firebase";
import { useParams } from "next/navigation";
import Link from "next/link";

export default function DocumentDetail() {
    const { id } = useParams();
    const [docItem, setDocItem] = useState<DocumentData | null>(null);
    const [childImages, setChildImages] = useState<DocumentData[]>([]);
    const [loading, setLoading] = useState(true);

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
            <Link href="/" className="text-indigo-600 hover:underline">Back to Archive</Link>
        </div>
    );

    return (
        <div className="min-h-screen bg-gray-50">
            {/* Nav */}
            <nav className="bg-white border-b border-gray-200 px-4 py-4 sm:px-6 lg:px-8 flex items-center justify-between sticky top-0 z-10">
                <Link href="/" className="flex items-center text-sm font-medium text-gray-500 hover:text-gray-900 transition-colors">
                    <span className="mr-2">←</span> Back
                </Link>
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
                                <p><span className="text-gray-400">Filename:</span> <span className="font-mono">{docItem.filename}</span></p>
                                <p><span className="text-gray-400">Ingested:</span> {docItem.ingested_at ? new Date(docItem.ingested_at.seconds * 1000).toLocaleDateString() : 'N/A'}</p>
                            </div>
                        </div>
                    </div>

                    {/* Right: Extracted Photos Gallery */}
                    <div className="lg:col-span-2">
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
                    </div>
                </div>
            </main>
        </div>
    );
}
