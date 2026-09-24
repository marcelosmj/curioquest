package com.curioquest.servidor

import android.Manifest
import android.content.pm.PackageManager
import android.graphics.Color
import android.os.Build
import android.os.Bundle
import android.view.Gravity
import android.widget.*
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat

class MainActivity : AppCompatActivity() {

    private lateinit var estado: TextView
    private lateinit var botao: Button

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        if (Build.VERSION.SDK_INT >= 33 &&
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.POST_NOTIFICATIONS), 1)
        }

        val raiz = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            setPadding(60, 60, 60, 60)
        }

        raiz.addView(TextView(this).apply {
            text = "Servidor Curio Quest"
            textSize = 24f
            gravity = Gravity.CENTER
        })

        estado = TextView(this).apply {
            text = "Parado"
            textSize = 16f
            gravity = Gravity.CENTER
            setPadding(0, 40, 0, 40)
        }
        raiz.addView(estado)

        botao = Button(this).apply {
            text = "Iniciar servidor"
            setOnClickListener { alternar() }
        }
        raiz.addView(botao)

        raiz.addView(TextView(this).apply {
            text = "Deixe este app aberto ou em segundo plano e abra o Curio Quest.\n\n" +
                    "O servidor roda dentro do proprio aparelho: nao precisa de PC, " +
                    "cabo nem internet."
            textSize = 13f
            gravity = Gravity.CENTER
            setPadding(0, 60, 0, 0)
            setTextColor(Color.GRAY)
        })

        setContentView(raiz)
        atualizar()
    }

    private fun alternar() {
        if (ServidorService.rodando) ServidorService.parar(this) else ServidorService.iniciar(this)
        botao.postDelayed({ atualizar() }, 1500)
    }

    private fun atualizar() {
        val ligado = ServidorService.rodando
        estado.text = if (ligado) "No ar - abra o Curio Quest" else "Parado"
        botao.text = if (ligado) "Parar servidor" else "Iniciar servidor"
    }

    override fun onResume() {
        super.onResume()
        atualizar()
    }
}
