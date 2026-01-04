"use client";

import { useEffect, useState, useRef } from "react";
import { doc, getDoc } from "firebase/firestore";
import { db } from "@/lib/firebase";
import Link from "next/link";

// ... imports
interface FaceCardProps {
    face: any;
    imageUrl?: string | null;
    onMouseEnter?: () => void;
    onMouseLeave?: () => void;
}

export default function FaceCard({ face, imageUrl: providedImageUrl, onMouseEnter, onMouseLeave }: FaceCardProps) {
    const [fetchedImageUrl, setFetchedImageUrl] = useState<string | null>(null);
    const imageUrl = providedImageUrl ?? fetchedImageUrl;
    const [style, setStyle] = useState<React.CSSProperties>({ opacity: 0 });
    const imgRef = useRef<HTMLImageElement>(null);
    // ...

    useEffect(() => {
        if (providedImageUrl) return;

        const fetchImage = async () => {
            if (!face.parent_image_id) return;
            try {
                const docRef = doc(db, "images", face.parent_image_id);
                const snap = await getDoc(docRef);
                if (snap.exists()) {
                    const data = snap.data();
                    setFetchedImageUrl(data.preview_medium || data.preview_thumb);
                }
            } catch (e) {
                console.error(e);
            }
        };
        fetchImage();
    }, [face.parent_image_id, providedImageUrl]);

    const calculateStyle = (img?: HTMLImageElement) => {
        if (!face.bbox || face.bbox.length !== 4) return;

        let [x1, y1, x2, y2] = face.bbox;

        let isNormalized = x1 <= 2.0 && y1 <= 2.0 && x2 <= 2.0 && y2 <= 2.0;

        // If not likely normalized, and we have image dimensions, normalize them
        if (!isNormalized && img) {
            const nw = img.naturalWidth;
            const nh = img.naturalHeight;
            if (nw && nh) {
                x1 /= nw;
                x2 /= nw;
                y1 /= nh;
                y2 /= nh;
                isNormalized = true;
            }
        }

        if (!isNormalized) return; // Can't calculate yet

        const w = x2 - x1;
        const h = y2 - y1;

        if (w <= 0 || h <= 0) return;

        // Scale: We want the face to be clearly visible.
        // A scale of 1.0 means the face width equals the container width.
        // A scale of 1.5 means we show 1.5x the face width (zoomed out context).
        const scaleFactor = 1.5;

        // Image Width in % relative to container
        // If face is 0.1 (10%) of image, to make face 100% of container, Image must be 1000%.
        // To make face 1/1.5 (66%) of container, Image must be 1000%/1.5 = 666%.
        const widthPercent = (1 / w) * 100 / scaleFactor;

        // Centering:
        // We want the Center of the Face (cx) to be at the Center of the Container (50%).
        // cx = x1 + w/2.
        // We translate the image. 
        // A translate of -50% moves the image center to the container left edge? No.
        // translate % is relative to the ELEMENT (the huge image).
        // If we want a point P (in 0-1 image coords) to be at Container Center (0.5 container):
        // Position of P in container pixels = P * ImgWidth + TranslatePixel.
        // We want P * ImgWidth + TranslatePixel = 0.5 * ContainerWidth.
        // TranslatePixel = 0.5 * ContainerWidth - P * ImgWidth.
        // Translate% = TranslatePixel / ImgWidth = 0.5 * (ContainerWidth/ImgWidth) - P.
        // Ratio ContainerWidth/ImgWidth = 1 / (widthPercent/100) = (w * scaleFactor).
        // Translate% = 0.5 * (w * scaleFactor) - (x1 + w/2).
        // Translate% = 0.5 * w * scaleFactor - x1 - 0.5 * w.
        // Translate% = -x1 + 0.5 * w * (scaleFactor - 1).

        const tx = -x1 + 0.5 * w * (scaleFactor - 1);
        const ty = -y1 + 0.5 * h * (scaleFactor - 1);

        setStyle({
            width: `${widthPercent}%`,
            maxWidth: 'none',
            transform: `translate(${tx * 100}%, ${ty * 100}%)`,
            opacity: 1,
            transition: 'opacity 0.3s'
        });
    };

    // Try calculating on mount if normalized
    useEffect(() => {
        calculateStyle();
    }, [face.bbox]);

    const handleLoad = () => {
        if (imgRef.current) {
            calculateStyle(imgRef.current);
        }
    };

    return (
        <Link
            href={`/faces/${face.id}`}
            className="block aspect-square bg-zinc-900 rounded-lg overflow-hidden relative group border border-zinc-800 hover:border-emerald-500 transition-colors"
            onMouseEnter={onMouseEnter}
            onMouseLeave={onMouseLeave}
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
