"use server";

import { initializeApp, getApps, cert } from "firebase-admin/app";
import { getFirestore } from "firebase-admin/firestore";

// Initialize Firebase Admin
// Note: In Next.js server actions, this runs on the server.
// We need SERVICE_ACCOUNT_KEY env var or similar. 
// For this environment, we might rely on default creds or specific setup.
// Assuming client has set up GOOGLE_APPLICATION_CREDENTIALS or similar.

const serviceAccount = process.env.FIREBASE_SERVICE_ACCOUNT_KEY
    ? JSON.parse(process.env.FIREBASE_SERVICE_ACCOUNT_KEY)
    : null;

if (!getApps().length) {
    if (serviceAccount) {
        initializeApp({
            credential: cert(serviceAccount)
        });
    } else {
        initializeApp();
    }
}

const adminDb = getFirestore();

export async function findSimilarFaces(faceId: string) {
    try {
        // 1. Get the target face to get its embedding
        const faceDoc = await adminDb.collection("faces").doc(faceId).get();
        if (!faceDoc.exists) {
            return { error: "Face not found" };
        }

        const faceData = faceDoc.data();
        const embedding = faceData?.embedding; // This should be a Vector object or array?

        // In Firestore, Vector type is an object.
        // But for vector search queries we need...
        // We need to use `findNearest`

        if (!embedding) {
            return { error: "No embedding found for this face" };
        }

        // 2. Perform Vector Search
        // Query for 10 nearest neighbors
        const coll = adminDb.collection("faces");
        const vectorQuery = coll.findNearest('embedding', embedding, {
            limit: 20,
            distanceMeasure: 'COSINE'
        });

        const snapshot = await vectorQuery.get();

        const results = snapshot.docs.map(doc => {
            const data = doc.data();
            // Serialize Timestamp to string and remove embedding (Vector object)
            const { embedding, ingested_at, ...rest } = data;

            return {
                id: doc.id,
                ...rest,
                ingested_at: (ingested_at && typeof ingested_at.toDate === 'function')
                    ? ingested_at.toDate().toISOString()
                    : ingested_at,
            };
        });

        // Filter out the query face itself
        const filtered = results.filter(f => f.id !== faceId);

        return { faces: filtered };

    } catch (error: any) {
        console.error("Vector Search Error:", error);
        return { error: error.message };
    }
}
