package com.example.androidapp;

import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.widget.Button;
import android.widget.ImageView;
import android.widget.TextView;

import androidx.activity.ComponentActivity;
import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

import okhttp3.MediaType;
import okhttp3.MultipartBody;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;

public class DecodeUploadActivity extends ComponentActivity {

    private static final String DECODE_URL = "https://api.roadscript.studio/decode";

    private final OkHttpClient client = new OkHttpClient();
    private final ExecutorService executor = Executors.newSingleThreadExecutor();

    private Uri selectedUri;

    private ImageView imgPreview;
    private TextView tvStatus;
    private Button btnDecode;

    private ActivityResultLauncher<String> pickImageLauncher;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_decode_upload);

        imgPreview = findViewById(R.id.imgPreview);
        tvStatus = findViewById(R.id.tvStatus);
        Button btnSelect = findViewById(R.id.btnSelect);
        btnDecode = findViewById(R.id.btnDecode);

        pickImageLauncher = registerForActivityResult(
                new ActivityResultContracts.GetContent(),
                uri -> {
                    if (uri == null) return;
                    selectedUri = uri;
                    imgPreview.setImageURI(uri);
                    btnDecode.setEnabled(true);
                    tvStatus.setText("Status: image selected");
                }
        );

        btnSelect.setOnClickListener(v -> pickImageLauncher.launch("image/*"));

        btnDecode.setOnClickListener(v -> {
            if (selectedUri == null) return;
            btnDecode.setEnabled(false);
            tvStatus.setText("Status: decoding...");
            decodeOnServer(selectedUri);
        });
    }

    private void decodeOnServer(Uri uri) {
        executor.execute(() -> {
            try {
                byte[] imgBytes = readAllBytesFromUri(uri);
                if (imgBytes == null || imgBytes.length == 0) {
                    runOnUiThread(() -> {
                        tvStatus.setText("Status: failed to read image");
                        btnDecode.setEnabled(true);
                    });
                    return;
                }

                RequestBody fileBody = RequestBody.create(
                        imgBytes,
                        MediaType.parse("image/jpeg")
                );

                // ✅ /decode 只需要 file（step/key 可选），不需要 payload
                MultipartBody requestBody = new MultipartBody.Builder()
                        .setType(MultipartBody.FORM)
                        .addFormDataPart("file", "watermarked.jpg", fileBody)
                        .addFormDataPart("step", "30")   // 可选：默认 30
                        .addFormDataPart("key", "")      // 可选：不需要就空
                        .build();

                Request request = new Request.Builder()
                        .url(DECODE_URL)
                        .post(requestBody)
                        .build();

                try (Response response = client.newCall(request).execute()) {
                    String bodyStr = response.body() != null ? response.body().string() : "";

                    if (!response.isSuccessful()) {
                        runOnUiThread(() -> {
                            tvStatus.setText("HTTP " + response.code() + "\n" + bodyStr);
                            btnDecode.setEnabled(true);
                        });
                        return;
                    }

                    // 解析 JSON: {"ok":..., "message":..., "detail":...}
                    String decodedMessage = "(empty)";
                    boolean ok = false;

                    try {
                        JSONObject obj = new JSONObject(bodyStr);
                        ok = obj.optBoolean("ok", false);

                        // message 可能是 null
                        if (!obj.isNull("message")) {
                            decodedMessage = obj.optString("message", "(empty)");
                        } else {
                            decodedMessage = "(null)";
                        }

                        if (!ok) {
                            // 如果失败，把 detail 也带上方便你看原因
                            JSONObject detail = obj.optJSONObject("detail");
                            if (detail != null) {
                                decodedMessage = "Decode failed.\n\nDetail:\n" + detail.toString();
                            } else {
                                decodedMessage = "Decode failed.\n\nRaw:\n" + bodyStr;
                            }
                        }

                    } catch (Exception parseErr) {
                        // 不是 JSON 就直接显示原文
                        decodedMessage = bodyStr.isEmpty() ? "(empty)" : bodyStr;
                    }

                    String finalMsg = decodedMessage;
                    runOnUiThread(() -> {
                        tvStatus.setText("Status: decoded");
                        Intent intent = new Intent(this, DecodeResultActivity.class);
                        intent.putExtra("image_uri", uri.toString());
                        intent.putExtra("decoded_message", finalMsg);
                        startActivity(intent);
                        btnDecode.setEnabled(true);
                    });
                }

            } catch (Exception e) {
                runOnUiThread(() -> {
                    tvStatus.setText("Exception:\n" + e.getMessage());
                    btnDecode.setEnabled(true);
                });
            }
        });
    }

    private byte[] readAllBytesFromUri(Uri uri) throws Exception {
        try (InputStream is = getContentResolver().openInputStream(uri);
             ByteArrayOutputStream bos = new ByteArrayOutputStream()) {
            if (is == null) return null;
            byte[] buf = new byte[8192];
            int r;
            while ((r = is.read(buf)) != -1) bos.write(buf, 0, r);
            return bos.toByteArray();
        }
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        executor.shutdownNow();
    }
}