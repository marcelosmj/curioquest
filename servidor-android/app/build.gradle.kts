plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("com.chaquo.python")
}

android {
    namespace = "com.curioquest.servidor"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.curioquest.servidor"
        minSdk = 24
        targetSdk = 34
        versionCode = 1
        versionName = "1.0"
        // O APK do jogo e 32 bits (armeabi-v7a), mas os dois apps so conversam por TCP
        // no localhost, entao a arquitetura nao precisa bater.  O Python do Chaquopy so
        // existe para 64 bits, o que exclui aparelhos antigos somente-32-bits.
        ndk { abiFilters += listOf("arm64-v8a", "x86_64") }
    }

    buildTypes {
        release { isMinifyEnabled = false }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    // o APK original vai inteiro dentro de assets/ e NAO pode ser recomprimido:
    // o servidor o abre como zip em tempo de execucao
    androidResources { noCompress += "apk" }
}

// O servidor tem UMA origem: ../server.  Copiar no build evita manter uma segunda
// copia aqui dentro, que divergiria em silencio e so apareceria como bug no celular.
val raiz = rootProject.projectDir.parentFile

val sincronizarPython = tasks.register<Sync>("sincronizarPython") {
    from("$raiz/server") { exclude("content/**", "saves/**", "**/__pycache__/**") }
    into(layout.buildDirectory.dir("curioquest/python/server"))
}

val sincronizarDados = tasks.register<Sync>("sincronizarDados") {
    into(layout.buildDirectory.dir("curioquest/assets"))
    from("$raiz/server/content") {
        include("books/**", "web/**", "asset_aliases.json")
        into("content")
    }
    from("$raiz/server/es5") {
        include("es_constants.json", "thrift_spec.json")
        into("content")
    }
    // o APK original e a fonte dos assets do jogo em tempo de execucao
    from(raiz) { include("Curio Quest_1.15.00.apk"); rename { "CurioQuest.apk" } }
}

android.sourceSets.getByName("main").assets.srcDir(layout.buildDirectory.dir("curioquest/assets"))
tasks.matching { it.name.startsWith("merge") && it.name.contains("Assets") }
    .configureEach { dependsOn(sincronizarDados) }
tasks.matching {
    !it.name.startsWith("sincronizar") &&
        (it.name.contains("Python") || it.name.contains("Chaquopy"))
}.configureEach { dependsOn(sincronizarPython) }

chaquopy {
    defaultConfig {
        version = "3.12"
    }
    sourceSets { getByName("main") {
        srcDir("src/main/python")
        srcDir(layout.buildDirectory.dir("curioquest/python"))
    } }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
}
