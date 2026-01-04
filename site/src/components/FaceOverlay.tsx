"use client";

import { useEffect, useState, RefObject } from "react";
import { collection, query, where, getDocs, DocumentData } from "firebase/firestore";
import { db } from "@/lib/firebase";
import Link from "next/link";

interface FaceOverlayProps {
    imageId: string;
    imgRef: RefObject<HTMLImageElement | null>;
    faces: DocumentData[];
    hoveredFaceId?: string | null;
    onHover?: (id: string | null) => void;
}

export default function FaceOverlay({ imageId, imgRef, faces, hoveredFaceId, onHover }: FaceOverlayProps) {
    const [scale, setScale] = useState({ x: 1, y: 1 });
    const [dims, setDims] = useState({ width: 0, height: 0, top: 0, left: 0 });
    const [loaded, setLoaded] = useState(false);

    // Fetching removed, receiving faces via props


    // Handle resizing and scaling
    useEffect(() => {
        const updateOverlay = () => {
            const img = imgRef.current;
            if (!img || !img.complete) return;

            const rect = img.getBoundingClientRect();

            // Calculate scale: displayed size / natural size
            // Note: naturalWidth/Height might be 0 if image not loaded, handled by check above
            if (img.naturalWidth && img.naturalHeight) {
                setScale({
                    x: rect.width / img.naturalWidth,
                    y: rect.height / img.naturalHeight
                });
                setDims({
                    width: rect.width,
                    height: rect.height,
                    top: img.offsetTop,     // Use offsetTop/Left relative to offsetParent (container)
                    left: img.offsetLeft
                });
                setLoaded(true);
            }
        };

        const img = imgRef.current;
        if (!img) return;

        // Initial check
        if (img.complete) updateOverlay();

        // Listen for load
        img.addEventListener('load', updateOverlay);

        // Listen for resize
        const resizeObserver = new ResizeObserver(() => updateOverlay());
        resizeObserver.observe(img);
        window.addEventListener('resize', updateOverlay);

        return () => {
            img.removeEventListener('load', updateOverlay);
            resizeObserver.disconnect();
            window.removeEventListener('resize', updateOverlay);
        };
    }, [imgRef, faces]); // Re-run if faces change? No, faces don't affect scale. But imgRef does.

    if (!loaded || faces.length === 0) return null;

    return (
        <div
            className="absolute pointer-events-none"
            style={{
                top: dims.top,
                left: dims.left,
                width: dims.width,
                height: dims.height,
            }}
        >
            {faces.map((face) => {
                const bbox = face.bbox; // [x1, y1, x2, y2]
                if (!bbox || bbox.length !== 4) return null;

                const [x1, y1, x2, y2] = bbox;

                // Check if bbox is normalized (0.0 - 1.0)
                // Heuristic: if all coordinates are <= 1.5, assume normalized
                const isNormalized = x1 <= 2.0 && y1 <= 2.0 && x2 <= 2.0 && y2 <= 2.0;

                let boxStyle;
                if (isNormalized) {
                    boxStyle = {
                        left: x1 * dims.width,
                        top: y1 * dims.height,
                        width: (x2 - x1) * dims.width,
                        height: (y2 - y1) * dims.height,
                    };
                } else {
                    // Legacy: Absolute pixels relative to natural size
                    boxStyle = {
                        left: x1 * scale.x,
                        top: y1 * scale.y,
                        width: (x2 - x1) * scale.x,
                        height: (y2 - y1) * scale.y,
                    };
                }

                const isHovered = hoveredFaceId === face.id;

                return (
                    <Link
                        key={face.id}
                        href={`/faces/${face.id}`}
                        className={`absolute border-2 transition-colors cursor-pointer pointer-events-auto group ${isHovered
                            ? "border-emerald-300 bg-emerald-400/30 z-20"
                            : "border-emerald-400/70 hover:border-emerald-400 hover:bg-emerald-400/10 z-10"
                            }`}
                        style={{
                            left: `${boxStyle.left}px`,
                            top: `${boxStyle.top}px`,
                            width: `${boxStyle.width}px`,
                            height: `${boxStyle.height}px`,
                        }}
                        title={`Face ${face.id} (Score: ${face.det_score?.toFixed(2)})`}
                        onMouseEnter={() => onHover?.(face.id)}
                        onMouseLeave={() => onHover?.(null)}
                    >
                        {/* Optional: Show score or details on hover */}
                        {/* <div className="absolute -top-6 left-0 bg-black/70 text-white text-[10px] px-1 rounded opacity-0 group-hover:opacity-100 whitespace-nowrap">
                             {(face.det_score * 100).toFixed(0)}%
                         </div> */}
                    </Link>
                );
            })}
        </div>
    );
}
