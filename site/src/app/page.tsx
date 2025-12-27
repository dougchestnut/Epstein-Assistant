export default function Home() {
    return (
        <div className="min-h-[calc(100vh-100px)]">
            <div className="bg-white shadow overflow-hidden sm:rounded-lg">
                <div className="px-4 py-5 sm:px-6">
                    <h1 className="text-3xl font-bold leading-tight text-gray-900">
                        Archive Dashboard
                    </h1>
                    <p className="mt-1 max-w-2xl text-sm text-gray-500">
                        Overview of the collected documents and media.
                    </p>
                </div>
                <div className="border-t border-gray-200 px-4 py-5 sm:p-0">
                    <div className="p-6 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
                        {/* Stats Cards Placeholders */}
                        <div className="bg-indigo-50 overflow-hidden rounded-lg shadow p-5">
                            <dt className="text-sm font-medium text-gray-500 truncate">Total Documents</dt>
                            <dd className="mt-1 text-3xl font-semibold text-indigo-600">--</dd>
                        </div>
                        <div className="bg-indigo-50 overflow-hidden rounded-lg shadow p-5">
                            <dt className="text-sm font-medium text-gray-500 truncate">Processed Images</dt>
                            <dd className="mt-1 text-3xl font-semibold text-indigo-600">--</dd>
                        </div>
                        <div className="bg-indigo-50 overflow-hidden rounded-lg shadow p-5">
                            <dt className="text-sm font-medium text-gray-500 truncate">Media Files</dt>
                            <dd className="mt-1 text-3xl font-semibold text-indigo-600">--</dd>
                        </div>
                    </div>
                    <div className="p-6">
                        <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">Quick Actions</h3>
                        <div className="flex gap-4">
                            <a href="/browse" className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700">
                                Browse Collection
                            </a>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
