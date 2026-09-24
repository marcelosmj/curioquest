package com.curioquest.servidor

import android.app.*
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.IBinder
import android.util.Log
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.io.File

/**
 * Sobe o servidor Python e o mantem vivo enquanto o jogador esta no jogo.
 *
 * Precisa ser um servico em primeiro plano: o jogador abre este app e troca
 * imediatamente para o Curio Quest, e o Android encerraria um servico comum
 * nesse momento - justo quando o jogo comeca a falar com ele.
 */
class ServidorService : Service() {

    companion object {
        const val CANAL = "servidor"
        var rodando = false
            private set

        fun iniciar(ctx: Context) = ctx.startForegroundService(Intent(ctx, ServidorService::class.java))
        fun parar(ctx: Context) = ctx.stopService(Intent(ctx, ServidorService::class.java))
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        startForeground(1, notificacao("Iniciando..."))
        Thread { subirPython() }.start()
    }

    private fun subirPython() {
        try {
            if (!Python.isStarted()) Python.start(AndroidPlatform(this))
            val py = Python.getInstance()

            // O servidor le os assets do jogo de dentro do APK original, que viaja
            // dentro deste app.  E preciso copia-lo para um caminho real, porque
            // assets/ nao e um arquivo no sistema de arquivos.
            val apk = File(filesDir, "CurioQuest.apk")
            if (!apk.exists() || apk.length() == 0L) {
                assets.open("CurioQuest.apk").use { entrada ->
                    apk.outputStream().use { entrada.copyTo(it) }
                }
            }

            // livros, conteudo web e es_constants.json: o Chaquopy nao entrega arquivos
            // de dados como arquivos reais, entao eles viajam em assets/ e sao extraidos
            val conteudo = File(filesDir, "content")
            if (!File(conteudo, "es_constants.json").exists()) copiarAssets("content", conteudo)

            val saves = File(filesDir, "saves").apply { mkdirs() }
            py.getModule("android_main").callAttr(
                "iniciar", apk.absolutePath, saves.absolutePath, conteudo.absolutePath
            )
            rodando = true
            notificar("Servidor no ar - abra o Curio Quest")
            Log.i("ServidorCQ", "servidor iniciado")
        } catch (e: Throwable) {
            Log.e("ServidorCQ", "falhou ao iniciar", e)
            notificar("Falhou: ${e.message}")
        }
    }

    /** Copia uma pasta de assets/ para o disco, recursivamente. */
    private fun copiarAssets(origem: String, destino: File) {
        val filhos = assets.list(origem) ?: return
        if (filhos.isEmpty()) {
            destino.parentFile?.mkdirs()
            assets.open(origem).use { entrada -> destino.outputStream().use { entrada.copyTo(it) } }
            return
        }
        destino.mkdirs()
        for (filho in filhos) copiarAssets("$origem/$filho", File(destino, filho))
    }

    private fun notificacao(texto: String): Notification {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val canal = NotificationChannel(CANAL, "Servidor", NotificationManager.IMPORTANCE_LOW)
            getSystemService(NotificationManager::class.java).createNotificationChannel(canal)
        }
        val abrir = PendingIntent.getActivity(
            this, 0, Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE
        )
        return Notification.Builder(this, CANAL)
            .setContentTitle("Servidor Curio Quest")
            .setContentText(texto)
            .setSmallIcon(android.R.drawable.stat_sys_download_done)
            .setContentIntent(abrir)
            .setOngoing(true)
            .build()
    }

    private fun notificar(texto: String) =
        getSystemService(NotificationManager::class.java).notify(1, notificacao(texto))

    override fun onDestroy() {
        rodando = false
        super.onDestroy()
    }
}
