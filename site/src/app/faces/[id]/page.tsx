"use client";

import { useEffect, useState, useRef } from "react";
import { doc, getDoc, DocumentData } from "firebase/firestore";
import { db } from "@/lib/firebase";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { findSimilarFaces } from "@/lib/actions";
import FaceCard from "@/components/FaceCard";

export default function FaceDetail() {
    const { id } = useParams();
    const router = useRouter();
    const [face, setFace] = useState<DocumentData | null>(null);
    const [similarFaces, setSimilarFaces] = useState<DocumentData[]>([]);
    const [loading, setLoading] = useState(true);
    const [searching, setSearching] = useState(true);
    const [parentImage, setParentImage] = useState<DocumentData | null>(null);

    // Fetch Face Data
    useEffect(() => {
        if (!id) return;
        const fetchData = async () => {
            try {
                // Get Face
                const docRef = doc(db, "faces", id as string);
                const docSnap = await getDoc(docRef);

                if (docSnap.exists()) {
                    const faceData = docSnap.data();
                    setFace({ id: docSnap.id, ...faceData });

                    // Get Parent Image
                    if (faceData.parent_image_id) {
                        const imgRef = doc(db, "images", faceData.parent_image_id);
                        const imgSnap = await getDoc(imgRef);
                        if (imgSnap.exists()) {
                            setParentImage({ id: imgSnap.id, ...imgSnap.data() });
                        }
                    }
                }
            } catch (err) {
                console.error("Error fetching data:", err);
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, [id]);

    // Perform Vector Search (Server Action)
    useEffect(() => {
        if (!id) return;

        const search = async () => {
            setSearching(true);
            try {
                // Call Server Action
                const result = await findSimilarFaces(id as string);
                if (result.faces) {
                    setSimilarFaces(result.faces);
                } else if (result.error) {
                    console.warn("Vector search error:", result.error);
                }
            } catch (err) {
                console.error("Vector Search failed:", err);
            } finally {
                setSearching(false);
            }
        };

        // Wait for face to be loaded first? Not strictly necessary if ID is valid,
        // but cleaner UI flow.
        search();

    }, [id]);

    if (loading) return (
        <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
            <div className="w-8 h-8 border-4 border-zinc-700 border-t-emerald-500 rounded-full animate-spin"></div>
        </div>
    );

    if (!face) return (
        <div className="min-h-screen bg-zinc-950 flex flex-col items-center justify-center text-zinc-400">
            <p className="mb-4">Face not found.</p>
            <button onClick={() => router.back()} className="text-emerald-400 hover:text-emerald-300 underline">Go Back</button>
        </div>
    );

    return (
        <div className="min-h-screen bg-zinc-950 text-zinc-100 p-6 lg:p-12">
            <nav className="mb-8 flex items-center gap-4">
                <button
                    onClick={() => router.back()}
                    className="flex items-center gap-2 text-zinc-500 hover:text-white transition-colors"
                >
                    <span>←</span> Back
                </button>
                <div className="text-zinc-700">|</div>
                <Link href="/faces" className="text-zinc-500 hover:text-white transition-colors">
                    Faces Index
                </Link>
            </nav>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-12">

                {/* Left: Face Detail */}
                <div className="space-y-8">
                    <div className="bg-zinc-900 rounded-xl p-6 border border-zinc-800 flex flex-col items-center">
                        <div className="w-64 h-64 mb-6 relative">
                            {/* Reuse FaceCard for consistent styling/cropping, or implement custom large view */}
                            {/* We need to pass the face object which has bbox and parent_image_id */}
                            <div className="w-full h-full">
                                <FaceCard face={face} />
                            </div>
                        </div>

                        <h1 className="text-xl font-bold text-center text-emerald-400 mb-2">
                            {face.name || "Unknown Face"}
                        </h1>
                        <p className="text-zinc-500 font-mono text-xs mb-6 max-w-xs text-center truncate">
                            ID: {id}
                        </p>

                        <div className="w-full space-y-4 border-t border-zinc-800 pt-6">
                            {/* Metadata */}
                            <div className="flex justify-between text-sm">
                                <span className="text-zinc-500">Detection Score</span>
                                <span className="font-mono text-zinc-300">{face.det_score?.toFixed(4)}</span>
                            </div>

                            {parentImage && (
                                <div className="space-y-1">
                                    <span className="text-xs text-zinc-500 uppercase tracking-wider">Source Image</span>
                                    <Link
                                        href={`/images/${parentImage.id}`}
                                        className="flex items-center gap-3 p-2 bg-zinc-800/50 hover:bg-zinc-800 rounded transition-colors group"
                                    >
                                        <div className="w-12 h-12 bg-black rounded overflow-hidden flex-shrink-0">
                                            <img src={parentImage.preview_thumb} className="w-full h-full object-cover" />
                                        </div>
                                        <div className="overflow-hidden">
                                            <p className="text-sm font-medium text-emerald-300 truncate group-hover:underline">
                                                {parentImage.image_name}
                                            </p>
                                            <p className="text-xs text-zinc-500">
                                                Page {parentImage.page_num}
                                            </p>
                                        </div>
                                    </Link>
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                {/* Right: Similar Faces */}
                <div className="lg:col-span-2">
                    <h2 className="text-2xl font-bold mb-6 flex items-center gap-3">
                        Similar Faces
                        {searching && (
                            <span className="text-xs font-normal text-zinc-500 animate-pulse">Searching...</span>
                        )}
                    </h2>

                    {!searching && similarFaces.length === 0 ? (
                        <div className="p-12 border border-dashed border-zinc-800 rounded-xl text-center text-zinc-600">
                            No similar faces found or Vector Search is not enabled yet.
                        </div>
                    ) : (
                        <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-5 gap-4">
                            {similarFaces.map(simFace => (
                                <div key={simFace.id} className="relative group">
                                    <FaceCard face={simFace} />
                                    {/* Optional: Show distance/similarity score if available */}
                                    {/* Firestore `findNearest` results don't typically include distance in the doc data, 
                                        unless we manually merge it. The API returns it in metadata in some SDKs 
                                        but `snapshot.docs` might not expose it directly in plain object map. 
                                        We might need to adjust the server action to return it. */}
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
