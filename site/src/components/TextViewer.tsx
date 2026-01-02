"use client";

import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";

interface TextViewerProps {
    url?: string;
    content?: string; // Allow direct content too
    isMarkdown?: boolean;
    className?: string;
}

export default function TextViewer({ url, content: initialContent, isMarkdown, className = "" }: TextViewerProps) {
    const [text, setText] = useState<string | null>(initialContent || null);
    const [loading, setLoading] = useState(!!url && !initialContent);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!url || initialContent) return;

        setLoading(true);
        setError(null);

        fetch(url)
            .then(async (res) => {
                if (!res.ok) throw new Error("Failed to load content");
                return res.text();
            })
            .then((data) => {
                setText(data);
                setLoading(false);
            })
            .catch((err) => {
                console.error(err);
                setError("Could not load text content.");
                setLoading(false);
            });
    }, [url, initialContent]);

    if (loading) {
        return (
            <div className={`flex items-center justify-center p-12 bg-gray-50 border border-gray-100 rounded-lg ${className}`}>
                <div className="w-6 h-6 border-2 border-gray-300 border-t-indigo-500 rounded-full animate-spin"></div>
            </div>
        );
    }

    if (error) {
        return (
            <div className={`p-6 text-center text-red-500 bg-red-50 rounded-lg ${className}`}>
                <p>{error}</p>
            </div>
        );
    }

    if (!text) return null;

    // Determine render mode
    // If isMarkdown is not explicitly set, try to guess from URL? 
    // Usually passed explicitly is safer.

    return (
        <div className={`bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden ${className}`}>
            <div className="p-4 overflow-x-auto">
                {isMarkdown ? (
                    <article className="prose prose-sm max-w-none prose-indigo">
                        <ReactMarkdown>{text}</ReactMarkdown>
                    </article>
                ) : (
                    <pre className="text-xs sm:text-sm font-mono text-gray-800 whitespace-pre-wrap break-words">
                        {text}
                    </pre>
                )}
            </div>
        </div>
    );
}
