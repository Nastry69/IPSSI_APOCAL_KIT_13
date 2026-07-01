import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';

// Config Vite (build + dev). La config des tests vit dans vitest.config.ts.
export default defineConfig({
  plugins: [react()],
  server: {
    host: true, // accessible depuis l'hôte (utile en Docker)
    port: 3000,
    strictPort: true,
    // En Docker (surtout Windows/macOS), le watcher natif ne reçoit pas les
    // événements de modification des fichiers montés depuis l'hôte : le HMR
    // reste alors aveugle aux changements. Le polling force Vite à détecter les
    // modifs (léger coût CPU, standard pour le dev conteneurisé).
    watch: { usePolling: true, interval: 100 },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
});
