import React, { useState, useRef } from 'react';
import { UploadCloud, Image as ImageIcon, AlertTriangle, FileText, CheckCircle2 } from 'lucide-react';
import { EcgLoader } from '../common/EcgLoader';

interface ScanUploadDropzoneProps {
  onUpload: (file: File, mode: 'triage' | 'full') => Promise<void>;
  isUploading: boolean;
  uploadStage: number;
}

const ALLOWED_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.tiff', '.tif', '.bmp', '.dcm', '.dicom'];
const MAX_UPLOAD_BYTES = 20 * 1024 * 1024; // 20 MB

export const ScanUploadDropzone: React.FC<ScanUploadDropzoneProps> = ({
  onUpload,
  isUploading,
  uploadStage,
}) => {
  const [isDragOver, setIsDragOver] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (file: File) => {
    setErrorMsg(null);
    const ext = '.' + file.name.split('.').pop()?.toLowerCase();

    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      setErrorMsg(
        `Unsupported format '${ext}'. Allowed formats: PNG, JPG, JPEG, TIFF, BMP, DICOM (.dcm)`
      );
      return;
    }

    if (file.size > MAX_UPLOAD_BYTES) {
      setErrorMsg('File size exceeds maximum allowed limit of 20 MB.');
      return;
    }

    setSelectedFile(file);

    // Create client-side object URL for non-DICOM preview
    if (!ext.includes('dcm')) {
      const url = URL.createObjectURL(file);
      setPreviewUrl(url);
    } else {
      setPreviewUrl(null);
    }

    // Auto-trigger fast triage
    onUpload(file, 'triage');
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileChange(e.dataTransfer.files[0]);
    }
  };

  return (
    <div className="bg-canvas-card border border-edge rounded-xl p-6 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-lg font-semibold text-ink flex items-center gap-2">
            <ImageIcon className="w-5 h-5 text-teal-accent" />
            Upload Medical Scan / Radiograph
          </h2>
          <p className="text-xs text-ink-muted mt-0.5">
            Supports Chest X-rays, CT/MRI slices, and DICOM series (.dcm, .png, .jpg) up to 20 MB.
          </p>
        </div>
        <span className="text-[11px] font-mono bg-teal-accent/10 text-teal-accent px-2.5 py-1 rounded-full border border-teal-accent/20">
          BiomedCLIP Fast Triage Enabled
        </span>
      </div>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragOver(true);
        }}
        onDragLeave={() => setIsDragOver(false)}
        onDrop={handleDrop}
        onClick={() => !isUploading && fileInputRef.current?.click()}
        className={`relative border-2 border-dashed rounded-xl p-8 text-center transition-all duration-200 cursor-pointer ${
          isDragOver
            ? 'border-teal-accent bg-teal-accent/5 scale-[0.99]'
            : 'border-edge hover:border-teal-accent/60 hover:bg-canvas-subtle/50'
        } ${isUploading ? 'pointer-events-none opacity-80' : ''}`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".png,.jpg,.jpeg,.tiff,.bmp,.dcm,.dicom"
          className="hidden"
          onChange={(e) => e.target.files && e.target.files[0] && handleFileChange(e.target.files[0])}
        />

        {isUploading ? (
          <div className="py-4">
            <EcgLoader
              label={
                uploadStage === 1
                  ? 'Ingesting & Windowing Scan...'
                  : uploadStage === 2
                  ? 'Running BiomedCLIP Zero-Shot Fast Triage...'
                  : 'Corroborating with Report Knowledge Graph...'
              }
              sublabel="Encrypted AES-256-GCM private isolation active"
            />
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center gap-3">
            {previewUrl ? (
              <div className="relative w-28 h-28 rounded-lg overflow-hidden border border-edge shadow-md bg-black">
                <img src={previewUrl} alt="Preview" className="w-full h-full object-cover" />
                <div className="absolute inset-0 bg-black/30 flex items-center justify-center opacity-0 hover:opacity-100 transition-opacity">
                  <span className="text-[10px] text-white font-medium">Click to replace</span>
                </div>
              </div>
            ) : (
              <div className="w-14 h-14 rounded-full bg-teal-accent/10 border border-teal-accent/20 flex items-center justify-center text-teal-accent shadow-inner">
                <UploadCloud className="w-7 h-7 animate-pulse" />
              </div>
            )}

            <div>
              <p className="text-sm font-medium text-ink">
                {selectedFile ? selectedFile.name : 'Drop your medical scan here, or click to browse'}
              </p>
              <p className="text-xs text-ink-muted mt-1">
                PNG, JPG, BMP, TIFF, DICOM (.dcm) • Instant zero-shot triage (~200ms)
              </p>
            </div>
          </div>
        )}
      </div>

      {errorMsg && (
        <div className="mt-4 p-3 bg-rose-500/10 border border-rose-500/30 rounded-lg flex items-center gap-2.5 text-xs text-rose-400">
          <AlertTriangle className="w-4 h-4 flex-shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}
    </div>
  );
};
