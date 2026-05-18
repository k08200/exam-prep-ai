'use client';
import { useState, useCallback } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Trash2, FileText, Image, Presentation, FileType, Upload, AlertCircle } from 'lucide-react';
import { materialsApi } from '@/lib/api';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { formatFileSize, formatDate } from '@/lib/utils';
import type { Material } from '@/types';

interface MaterialsListProps {
  courseId: string;
  onUploadClick: () => void;
}

function getFileIcon(fileType: string, filename: string) {
  const lower = filename.toLowerCase();
  if (lower.endsWith('.pdf') || fileType === 'application/pdf') {
    return <FileText className="h-4 w-4 text-red-500" />;
  }
  if (lower.endsWith('.ppt') || lower.endsWith('.pptx')) {
    return <Presentation className="h-4 w-4 text-orange-500" />;
  }
  if (lower.endsWith('.doc') || lower.endsWith('.docx')) {
    return <FileType className="h-4 w-4 text-blue-500" />;
  }
  if (lower.endsWith('.png') || lower.endsWith('.jpg') || lower.endsWith('.jpeg')) {
    return <Image className="h-4 w-4 text-green-500" />;
  }
  return <FileText className="h-4 w-4 text-gray-400" />;
}

const STATUS_CONFIG: Record<
  Material['processing_status'],
  { label: string; className: string; dotClass: string }
> = {
  pending: {
    label: 'Pending',
    className: 'bg-amber-50 text-amber-700 border border-amber-200',
    dotClass: 'bg-amber-500',
  },
  processing: {
    label: 'Processing',
    className: 'bg-blue-50 text-blue-700 border border-blue-200',
    dotClass: 'bg-blue-500 animate-pulse',
  },
  completed: {
    label: 'Ready',
    className: 'bg-green-50 text-green-700 border border-green-200',
    dotClass: 'bg-green-500',
  },
  failed: {
    label: 'Failed',
    className: 'bg-red-50 text-red-700 border border-red-200',
    dotClass: 'bg-red-500',
  },
};

export function MaterialsList({ courseId, onUploadClick }: MaterialsListProps) {
  const queryClient = useQueryClient();
  const [materialToDelete, setMaterialToDelete] = useState<Material | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const { data: materials = [], isLoading } = useQuery<Material[]>({
    queryKey: ['materials', courseId],
    queryFn: async () => {
      const res = await materialsApi.list(courseId);
      return res.data;
    },
    refetchInterval: (query) => {
      const data = query.state.data as Material[] | undefined;
      if (!data) return false;
      const hasActive = data.some(
        (m) => m.processing_status === 'pending' || m.processing_status === 'processing'
      );
      return hasActive ? 3000 : false;
    },
  });

  const handleDelete = useCallback(
    async () => {
      if (!materialToDelete) return;
      setIsDeleting(true);
      setDeleteError(null);
      try {
        await materialsApi.delete(courseId, materialToDelete.id);
        queryClient.invalidateQueries({ queryKey: ['materials', courseId] });
        queryClient.invalidateQueries({ queryKey: ['courses'] });
        setMaterialToDelete(null);
      } catch (err: unknown) {
        const detail =
          err && typeof err === 'object' && 'response' in err
            ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
            : null;
        setDeleteError(detail || 'Failed to delete material. Please try again.');
      } finally {
        setIsDeleting(false);
      }
    },
    [courseId, materialToDelete, queryClient]
  );

  if (isLoading) {
    return (
      <div className="space-y-2">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-14 bg-gray-100 rounded-lg animate-pulse" />
        ))}
      </div>
    );
  }

  if (materials.length === 0) {
    return (
      <div className="text-center py-12 border-2 border-dashed border-gray-200 rounded-xl">
        <div className="flex justify-center mb-3">
          <div className="p-3 bg-gray-100 rounded-full">
            <Upload className="h-6 w-6 text-gray-400" />
          </div>
        </div>
        <p className="text-sm font-medium text-gray-600">No materials yet</p>
        <p className="text-xs text-gray-400 mt-1 mb-4">
          Upload lecture slides, notes, or past exams to get started
        </p>
        <Button size="sm" onClick={onUploadClick}>
          Upload Materials
        </Button>
      </div>
    );
  }

  return (
    <>
      <div className="overflow-hidden rounded-xl border border-gray-200">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200">
              <th className="text-left px-4 py-3 font-medium text-gray-600">File</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600 hidden sm:table-cell">
                Size
              </th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Status</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600 hidden md:table-cell">
                Pages
              </th>
              <th className="text-left px-4 py-3 font-medium text-gray-600 hidden lg:table-cell">
                Uploaded
              </th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {materials.map((material) => {
              const statusCfg = STATUS_CONFIG[material.processing_status];
              return (
                <tr key={material.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2.5">
                      {getFileIcon(material.file_type, material.original_filename)}
                      <span
                        className="font-medium text-gray-800 truncate max-w-[200px]"
                        title={material.original_filename}
                      >
                        {material.original_filename}
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-gray-500 hidden sm:table-cell">
                    {formatFileSize(material.file_size)}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium ${statusCfg.className}`}
                    >
                      <span className={`w-1.5 h-1.5 rounded-full ${statusCfg.dotClass}`} />
                      {statusCfg.label}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-500 hidden md:table-cell">
                    {material.page_count ?? '—'}
                  </td>
                  <td className="px-4 py-3 text-gray-400 hidden lg:table-cell">
                    {formatDate(material.created_at)}
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => {
                        setMaterialToDelete(material);
                        setDeleteError(null);
                      }}
                      className="p-1.5 rounded-lg text-gray-400 hover:text-red-500 hover:bg-red-50 transition-colors"
                      aria-label="Delete material"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <Modal
        isOpen={!!materialToDelete}
        onClose={() => {
          if (!isDeleting) {
            setMaterialToDelete(null);
            setDeleteError(null);
          }
        }}
        title="Delete Material"
        description="This removes the uploaded file from this course."
        size="sm"
      >
        <div className="space-y-4">
          <p className="text-sm text-gray-600 break-words">
            Delete <span className="font-medium text-gray-900">{materialToDelete?.original_filename}</span>?
          </p>
          {deleteError && (
            <div className="flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
              <AlertCircle className="h-4 w-4 flex-shrink-0 mt-0.5" />
              {deleteError}
            </div>
          )}
          <div className="flex justify-end gap-3">
            <Button
              variant="secondary"
              size="sm"
              disabled={isDeleting}
              onClick={() => {
                setMaterialToDelete(null);
                setDeleteError(null);
              }}
            >
              Cancel
            </Button>
            <Button variant="danger" size="sm" loading={isDeleting} onClick={handleDelete}>
              Delete Material
            </Button>
          </div>
        </div>
      </Modal>
    </>
  );
}
