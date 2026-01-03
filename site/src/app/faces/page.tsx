"use client";

import { useEffect, useState } from "react";
import { collection, query, orderBy, limit, getDocs, startAfter, DocumentData } from "firebase/firestore";
import { db } from "@/lib/firebase";
import FaceCard from "@/components/FaceCard";

export default function FacesPage() {
    const [faces, setFaces] = useState<DocumentData[]>([]);
    const [lastDoc, setLastDoc] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [loadingMore, setLoadingMore] = useState(false);

    const fetchFaces = async (isNext = false) => {
        try {
            const col = collection(db, "faces");
            let q = query(col, orderBy("det_score", "desc"), limit(48)); // Show best faces first

            if (isNext && lastDoc) {
                q = query(col, orderBy("det_score", "desc"), startAfter(lastDoc), limit(48));
            }

            const snap = await getDocs(q);
            const newFaces = snap.docs.map(doc => ({ id: doc.id, ...doc.data() }));

            if (isNext) {
                setFaces(prev => [...prev, ...newFaces]);
            } else {
                setFaces(newFaces);
            }

            setLastDoc(snap.docs[snap.docs.length - 1]);
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
            setLoadingMore(false);
        }
    };

    useEffect(() => {
        fetchFaces();
    }, []);

    return (
        <div className="min-h-screen bg-zinc-950 text-zinc-100">
            <nav className="p-6 border-b border-zinc-900 bg-zinc-950 sticky top-0 z-20 flex justify-between items-center">
                <h1 className="text-xl font-bold text-emerald-500">Detected Faces</h1>
                <div className="text-xs text-zinc-500">
                    Sorted by Detection Score
                </div>
            </nav>

            <main className="p-6">
                {loading ? (
                    <div className="flex justify-center py-20">
                        <div className="w-8 h-8 border-4 border-zinc-800 border-t-emerald-500 rounded-full animate-spin"></div>
                    </div>
                ) : (
                    <>
                        <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-8 gap-4">
                            {faces.map(face => (
                                <FaceCard key={face.id} face={face} />
                            ))}
                        </div>

                        {/* Load More Trigger */}
                        <div className="mt-12 flex justify-center">
                            <button
                                onClick={() => {
                                    setLoadingMore(true);
                                    fetchFaces(true);
                                }}
                                disabled={loadingMore}
                                className="px-6 py-2 bg-zinc-900 hover:bg-zinc-800 text-zinc-300 rounded-full text-sm font-medium transition-colors disabled:opacity-50"
                            >
                                {loadingMore ? "Loading..." : "Load More"}
                            </button>
                        </div>
                    </>
                )}
            </main>
        </div>
    );
}
