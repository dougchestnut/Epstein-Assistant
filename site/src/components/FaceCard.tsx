"use client";

import { useEffect, useState, useRef } from "react";
import { doc, getDoc } from "firebase/firestore";
import { db } from "@/lib/firebase";
import Link from "next/link";

interface FaceCardProps {
    face: any;
}

export default function FaceCard({ face }: FaceCardProps) {
    const [imageUrl, setImageUrl] = useState<string | null>(null);
    const [style, setStyle] = useState<React.CSSProperties>({ opacity: 0 });
    const imgRef = useRef<HTMLImageElement>(null);

    useEffect(() => {
        const fetchImage = async () => {
            if (!face.parent_image_id) return;
            // Try to use a cache or context in real app, but fetching here for MVP
            try {
                const docRef = doc(db, "images", face.parent_image_id);
                const snap = await getDoc(docRef);
                if (snap.exists()) {
                    const data = snap.data();
                    setImageUrl(data.preview_medium || data.preview_thumb);
                }
            } catch (e) {
                console.error(e);
            }
        };
        fetchImage();
    }, [face.parent_image_id]);

    const handleLoad = () => {
        const img = imgRef.current;
        if (!img || !face.bbox) return;

        const [x1, y1, x2, y2] = face.bbox;
        const faceW = x2 - x1;
        const faceH = y2 - y1;

        // We want the face to fill the container (e.g. 150x150)
        // Let's assume container is roughly square or we just fit 'cover'
        // Ideally we want to scale the image such that faceW becomes ContainerW

        // Since we don't know exact container size in pixels easily without ref, 
        // let's assume a target size or use a scale factor.
        // Better: Use styling to center the face.

        // Using a relative container, we can set Top/Left/Width %
        // BUT, we want to crop.

        // Approach:
        // Scale image so face is 100px wide (arbitrary base).
        // Translate so face top-left is at 0,0.

        // Let's just try to center the face in the view.
        // Viewport: 100% 100% of parent.

        // transform: translate(-x1 px, -y1 px) scale(k)
        // We need the natural size to know what x1 px is in rendered pixels?
        // No, x1 is in natural pixels (usually). verify `ingest`. Yes.

        const naturalW = img.naturalWidth;
        const naturalH = img.naturalHeight;

        // Prevent div by zero
        if (!naturalW || !faceW) return;

        // We want the face to be visible. 
        // Let's create a 'zoom' effect.
        // We can set the image width to (NaturalW / FaceW) * 100 %.
        // This makes the face 100% of the container width.

        const scale = 1.5; // Zoom out a bit so it's not JUST the face
        const wPercent = (naturalW / faceW) * 100 / scale;

        // Position:
        // We want x1 to be at left edge (or centered).
        // left = -(x1 / naturalW) * 100 * (naturalW / faceW) ... 
        // left = -(x1 / faceW) * 100%

        // Center it:
        // Face Center X = x1 + faceW/2
        // We want Face Center X to be at 50% of container.

        // Center calculations are tricky with percentages.
        // Simpler: 
        // width: `${(naturalW / faceW) * 100}%`
        // marginLeft: `-${(x1 / faceW) * 100}%`
        // marginTop: `-${(y1 / faceH) * 100}%` (assuming aspect ratio match)

        // But aspect ratios might not match.
        // Let's just try to fit width.

        const zoom = naturalW / (faceW * 2); // Show 2x face width area

        // This is getting complicated to be responsive.
        // Let's use `object-view-box` if supported? Chrome only.

        // Fallback:
        // absolute positioning.

        setStyle({
            width: `${(naturalW / faceW) * 100}%`,
            maxWidth: 'none',
            // Position so (x1, y1) is at (0,0)
            transform: `translate(-${(x1 / naturalW) * 100}%, -${(y1 / naturalH) * 100}%)`,
            // transform: `translate(-${x1}px, -${y1}px)`, // IF we knew pixels. We don't.

            // Actually, if we set width in %, then translate in % refers to the element's width (which is the big image).
            // So `translate(-${(x1/naturalW)*100}%)` moves it left by x1 pixels (scaled).
            // That aligns x1 with the left edge. Correct.

            opacity: 1,
            transition: 'opacity 0.3s'
        });
    };

    return (
        <Link
            href={`/faces/${face.id}`}
            className="block aspect-square bg-zinc-900 rounded-lg overflow-hidden relative group border border-zinc-800 hover:border-emerald-500 transition-colors"
        >
            {imageUrl && (
                <div className="w-full h-full relative overflow-hidden">
                    <img
                        ref={imgRef}
                        src={imageUrl}
                        alt=""
                        className="absolute top-0 left-0 origin-top-left"
                        style={style}
                        onLoad={handleLoad}
                    />
                </div>
            )}
            <div className="absolute inset-0 bg-gradient-to-t from-black/80 to-transparent opacity-0 group-hover:opacity-100 transition-opacity flex items-end p-2">
                <span className="text-xs text-emerald-400 font-mono text-ellipsis overflow-hidden whitespace-nowrap w-full">
                    {face.image_name}
                </span>
            </div>
        </Link>
    );
}
