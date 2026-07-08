'use client';
import { useState, useCallback, useRef, DragEvent, ChangeEvent } from 'react';
import {
  Upload,
  X,
  FileText,
  AlertCircle,
  CheckCircle,
  Image,
  Presentation,
  FileType,
  Loader2,
} from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { formatFileSize } from '@/lib/utils';
import { extractErrorMessage, materialsApi } from '@/lib/api';

const ACCEPTED_TYPES = [
  'application/pdf',
  'application/vnd.ms-powerpoint',
  'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  'application/msword',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'image/png',
  'image/jpeg',
];

const ACCEPTED_EXTENSIONS = ['.pdf', '.pptx', '.docx', '.png', '.jpg', '.jpeg'];
const LEGACY_OFFICE_EXTENSIONS: Record<string, string> = {
  '.ppt': 'Legacy .ppt files are not supported. Convert to .pptx and upload again.',
  '.doc': 'Legacy .doc files are not supported. Convert to .docx and upload again.',
};
const GENERIC_FILE_TYPES = ['', 'application/octet-stream', 'binary/octet-stream'];
const EXTENSION_TO_TYPES: Record<string, string[]> = {
  '.pdf': ['application/pdf'],
  '.pptx': [
    'application/vnd.ms-powerpoint',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  ],
  '.docx': [
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  ],
  '.png': ['image/png'],
  '.jpg': ['image/jpeg'],
  '.jpeg': ['image/jpeg'],
};
const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50MB
const MAX_UPLOAD_FILES = 10;

interface FileWithProgress {
  file: File;
  id: string;
  progress: number;
  status: 'pending' | 'uploading' | 'done' | 'error';
  error?: string;
}

interface FileUploadProps {
  courseId: string;
  onSuccess: () => void;
  onError: (message: string) => void;
}

function getFileIcon(file: File) {
  const name = file.name.toLowerCase();
  if (name.endsWith('.pdf')) return <FileText className="h-5 w-5 text-red-500" />;
  if (name.endsWith('.ppt') || name.endsWith('.pptx')) {
    return <Presentation className="h-5 w-5 text-orange-500" />;
  }
  if (name.endsWith('.doc') || name.endsWith('.docx')) {
    return <FileType className="h-5 w-5 text-blue-500" />;
  }
  if (name.endsWith('.png') || name.endsWith('.jpg') || name.endsWith('.jpeg')) {
    return <Image className="h-5 w-5 text-green-500" />;
  }
  return <FileText className="h-5 w-5 text-gray-400" />;
}

export function FileUpload({ courseId, onSuccess, onError }: FileUploadProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<FileWithProgress[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const progressIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const clearProgressInterval = useCallback(() => {
    if (progressIntervalRef.current) {
      clearInterval(progressIntervalRef.current);
      progressIntervalRef.current = null;
    }
  }, []);

  const validateFile = (file: File): string | null => {
    if (file.size > MAX_FILE_SIZE) {
      return `File exceeds 50MB limit (${formatFileSize(file.size)})`;
    }
    const lowerName = file.name.toLowerCase();
    const legacyExtension = Object.keys(LEGACY_OFFICE_EXTENSIONS).find((ext) =>
      lowerName.endsWith(ext)
    );
    if (legacyExtension) {
      return LEGACY_OFFICE_EXTENSIONS[legacyExtension];
    }

    const extension = ACCEPTED_EXTENSIONS.find((ext) => lowerName.endsWith(ext));
    if (!extension) {
      return 'Unsupported file type';
    }

    const fileType = file.type.toLowerCase();
    if (GENERIC_FILE_TYPES.includes(fileType)) return null;
    if (!ACCEPTED_TYPES.includes(fileType)) return 'Unsupported file type';

    const expectedTypes = EXTENSION_TO_TYPES[extension] || [];
    if (expectedTypes.length > 0 && !expectedTypes.includes(fileType)) {
      return `File type does not match the ${extension} extension`;
    }

    return null;
  };

  const addFiles = useCallback((newFiles: File[]) => {
    setSelectedFiles((prev) => {
      const existingKeys = new Set(prev.map((f) => `${f.file.name}-${f.file.size}`));
      let validCount = prev.filter((f) => f.status !== 'error').length;
      const unique: FileWithProgress[] = [];

      for (const file of newFiles) {
        const key = `${file.name}-${file.size}`;
        if (existingKeys.has(key)) continue;

        let error = validateFile(file);
        if (!error && validCount >= MAX_UPLOAD_FILES) {
          error = `Upload at most ${MAX_UPLOAD_FILES} files at a time`;
        }
        if (!error) validCount += 1;
        existingKeys.add(key);
        unique.push({
          file,
          id: `${file.name}-${file.size}-${Date.now()}-${Math.random()}`,
          progress: 0,
          status: error ? 'error' : 'pending',
          error: error ?? undefined,
        });
      }
      return [...prev, ...unique];
    });
  }, []);

  const handleDrop = useCallback(
    (e: DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setIsDragging(false);
      const droppedFiles = Array.from(e.dataTransfer.files);
      addFiles(droppedFiles);
    },
    [addFiles]
  );

  const handleDragOver = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback(() => {
    setIsDragging(false);
  }, []);

  const handleInputChange = useCallback(
    (e: ChangeEvent<HTMLInputElement>) => {
      if (e.target.files) {
        addFiles(Array.from(e.target.files));
        e.target.value = '';
      }
    },
    [addFiles]
  );

  const removeFile = (id: string) => {
    setSelectedFiles((prev) => prev.filter((f) => f.id !== id));
  };

  const uploadableFiles = selectedFiles.filter((f) => f.status === 'pending');

  const handleUpload = async () => {
    if (uploadableFiles.length === 0) return;
    clearProgressInterval();
    setIsUploading(true);

    // Mark all valid files as uploading
    setSelectedFiles((prev) =>
      prev.map((f) =>
        f.status === 'pending' ? { ...f, status: 'uploading', progress: 10 } : f
      )
    );

    try {
      // Simulate progress updates
      progressIntervalRef.current = setInterval(() => {
        setSelectedFiles((prev) =>
          prev.map((f) =>
            f.status === 'uploading' && f.progress < 80
              ? { ...f, progress: f.progress + 10 }
              : f
          )
        );
      }, 200);

      await materialsApi.upload(
        courseId,
        uploadableFiles.map((f) => f.file)
      );

      clearProgressInterval();

      setSelectedFiles((prev) =>
        prev.map((f) =>
          f.status === 'uploading' ? { ...f, status: 'done', progress: 100 } : f
        )
      );

      setTimeout(() => {
        setSelectedFiles([]);
        onSuccess();
      }, 800);
    } catch (err: unknown) {
      const message = extractErrorMessage(err, 'Upload failed. Please try again.');
      setSelectedFiles((prev) =>
        prev.map((f) =>
          f.status === 'uploading'
            ? { ...f, status: 'error', error: message, progress: 0 }
            : f
        )
      );
      onError(message);
    } finally {
      clearProgressInterval();
      setIsUploading(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Drop Zone */}
      <div
        className={`relative border-2 border-dashed rounded-xl p-8 text-center transition-all cursor-pointer ${
          isDragging
            ? 'border-blue-500 bg-blue-50'
            : 'border-gray-300 hover:border-blue-400 hover:bg-gray-50'
        }`}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ACCEPTED_EXTENSIONS.join(',')}
          className="hidden"
          onChange={handleInputChange}
        />
        <div className="flex flex-col items-center gap-3">
          <div
            className={`p-3 rounded-full ${
              isDragging ? 'bg-blue-100' : 'bg-gray-100'
            } transition-colors`}
          >
            <Upload
              className={`h-6 w-6 ${isDragging ? 'text-blue-600' : 'text-gray-400'}`}
            />
          </div>
          <div>
            <p className="text-sm font-medium text-gray-700">
              {isDragging ? 'Drop files here' : 'Drag & drop files or click to browse'}
            </p>
            <p className="text-xs text-gray-500 mt-1">
              PDF, PPTX, DOCX, PNG, JPG. Up to {MAX_UPLOAD_FILES} files,
              50MB each
            </p>
          </div>
          <div className="flex flex-wrap justify-center gap-1.5">
            {['PDF', 'PPTX', 'DOCX', 'PNG', 'JPG'].map((ext) => (
              <span
                key={ext}
                className="px-2 py-0.5 bg-gray-100 text-gray-600 text-xs rounded font-mono"
              >
                .{ext.toLowerCase()}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Selected Files */}
      {selectedFiles.length > 0 && (
        <div className="space-y-2">
          <p className="text-sm font-medium text-gray-700">
            {selectedFiles.length} file{selectedFiles.length > 1 ? 's' : ''} selected
          </p>
          <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
            {selectedFiles.map((fileItem) => (
              <div
                key={fileItem.id}
                className={`flex items-center gap-3 p-3 rounded-lg border ${
                  fileItem.status === 'error'
                    ? 'border-red-200 bg-red-50'
                    : fileItem.status === 'done'
                    ? 'border-green-200 bg-green-50'
                    : 'border-gray-200 bg-white'
                }`}
              >
                <span className="flex-shrink-0">{getFileIcon(fileItem.file)}</span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-800 truncate">
                    {fileItem.file.name}
                  </p>
                  <div className="flex items-center gap-2">
                    <p className="text-xs text-gray-500">
                      {formatFileSize(fileItem.file.size)}
                    </p>
                    {fileItem.error && (
                      <p className="text-xs text-red-600">{fileItem.error}</p>
                    )}
                  </div>
                  {/* Progress bar */}
                  {fileItem.status === 'uploading' && (
                    <div className="mt-1.5 h-1.5 bg-gray-200 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-blue-500 rounded-full transition-all duration-300"
                        style={{ width: `${fileItem.progress}%` }}
                      />
                    </div>
                  )}
                  {fileItem.status === 'done' && (
                    <div className="mt-1.5 h-1.5 bg-green-200 rounded-full overflow-hidden">
                      <div className="h-full bg-green-500 rounded-full w-full" />
                    </div>
                  )}
                </div>
                <div className="flex-shrink-0">
                  {fileItem.status === 'done' ? (
                    <CheckCircle className="h-4 w-4 text-green-500" />
                  ) : fileItem.status === 'error' ? (
                    <AlertCircle className="h-4 w-4 text-red-500" />
                  ) : fileItem.status === 'uploading' ? (
                    <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />
                  ) : (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        removeFile(fileItem.id);
                      }}
                      className="p-0.5 rounded text-gray-400 hover:text-red-500 hover:bg-red-50 transition-colors"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Upload Button */}
          <div className="flex justify-end gap-2 pt-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                setSelectedFiles([]);
                if (inputRef.current) inputRef.current.value = '';
              }}
              disabled={isUploading}
            >
              Clear All
            </Button>
            <Button
              size="sm"
              onClick={handleUpload}
              loading={isUploading}
              disabled={uploadableFiles.length === 0 || isUploading}
            >
              <FileText className="h-4 w-4" />
              Upload {uploadableFiles.length > 0 ? `${uploadableFiles.length} File${uploadableFiles.length > 1 ? 's' : ''}` : ''}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
