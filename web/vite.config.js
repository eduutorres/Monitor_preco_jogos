import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Em desenvolvimento (npm run dev) as chamadas /api vão para o Python em 8787.
// O build vai para ../dist: o host de C:\www serve em /Monitor_preco_jogos/ e o Python em http://localhost:8787
export default defineConfig({
  plugins: [react()],
  // caminhos relativos: o mesmo build funciona na raiz ou em /monitorprecojogos
  // (quem serve o index.html coloca <base href> com a pasta certa)
  base: './',
  server: { proxy: { '/api': 'http://localhost:8787' } },
  build: { outDir: '../dist', emptyOutDir: true },
})
