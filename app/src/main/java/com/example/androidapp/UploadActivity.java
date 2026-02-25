package com.example.androidapp;

import android.content.ContentValues;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.provider.MediaStore;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.TextView;
import android.widget.Toast;

import androidx.activity.ComponentActivity;
import androidx.exifinterface.media.ExifInterface;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

import okhttp3.Call;
import okhttp3.Callback;
import okhttp3.MediaType;
import okhttp3.MultipartBody;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;

public class UploadActivity extends ComponentActivity {

    private static final String SERVER_URL = "https://api.roadscript.studio/process";
    private static final String ALBUM_RELATIVE_PATH = "Pictures/WatermarkStudio";

    private ImageView imgPreview;
    private EditText etUsername;
    private Button btnUploadNow;
    private TextView tvStatus;
    private TextView tvCapturedTime;
    private TextView tvUsername;

    private Uri imageUri;

    private final OkHttpClient client = new OkHttpClient();
    private final ExecutorService bg = Executors.newSingleThreadExecutor();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_upload);

        imgPreview = findViewById(R.id.imgPreview);
        etUsername = findViewById(R.id.etUsername);
        btnUploadNow = findViewById(R.id.btnUploadNow);
        tvStatus = findViewById(R.id.tvStatus);
        tvCapturedTime = findViewById(R.id.tvCapturedTime);
        tvUsername = findViewById(R.id.tvUsername);

        imageUri = getIntent().getData();
        if (imageUri == null) {
            Toast.makeText(this, "No image selected", Toast.LENGTH_SHORT).show();
            finish();
            return;
        }

        imgPreview.setImageURI(imageUri);

        tvStatus.setText("");
        tvCapturedTime.setText("Time: Loading...");
        tvUsername.setText("Username: " + getUsername());

        String timeText = readExifTimeOrNow(imageUri);
        tvCapturedTime.setText("Time: " + timeText);

        etUsername.setOnFocusChangeListener((v, hasFocus) -> {
            if (!hasFocus) tvUsername.setText("Username: " + getUsername());
        });

        btnUploadNow.setOnClickListener(v -> uploadImage());
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        bg.shutdownNow();
    }

    private String getUsername() {
        String u = etUsername.getText().toString().trim();
        return u.isEmpty() ? "anonymous" : u;
    }

    private String readExifTimeOrNow(Uri uri) {
        try (InputStream is = getContentResolver().openInputStream(uri)) {
            if (is != null) {
                ExifInterface exif = new ExifInterface(is);
                String dt = exif.getAttribute(ExifInterface.TAG_DATETIME_ORIGINAL);
                if (dt == null) dt = exif.getAttribute(ExifInterface.TAG_DATETIME);
                if (dt != null && !dt.trim().isEmpty()) return dt.trim();
            }
        } catch (Exception ignored) {
        }
        return new SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.US).format(new Date());
    }

    private void uploadImage() {
        String username = getUsername();
        tvStatus.setText("Uploading...");

        bg.execute(() -> {
            byte[] imageBytes;
            try {
                imageBytes = readBytes(imageUri);
            } catch (Exception e) {
                runOnUiThread(() -> tvStatus.setText("Failed to read image"));
                return;
            }

            RequestBody fileBody = RequestBody.create(imageBytes, MediaType.parse("image/jpeg"));

            MultipartBody requestBody = new MultipartBody.Builder()
                    .setType(MultipartBody.FORM)
                    .addFormDataPart("file", "upload.jpg", fileBody)
                    .addFormDataPart("payload", username)
                    .build();

            Request request = new Request.Builder()
                    .url(SERVER_URL)
                    .post(requestBody)
                    .build();

            client.newCall(request).enqueue(new Callback() {
                @Override
                public void onFailure(Call call, java.io.IOException e) {
                    runOnUiThread(() -> tvStatus.setText("Upload failed: " + e.getMessage()));
                }

                @Override
                public void onResponse(Call call, Response response) {
                    try {
                        int code = response.code();
                        if (!response.isSuccessful()) {
                            String err = response.body() != null ? response.body().string() : "";
                            String msg = err.isEmpty() ? ("Server error: " + code) : ("Server error: " + code + " " + err);
                            runOnUiThread(() -> tvStatus.setText(msg));
                            return;
                        }

                        String ct = response.header("Content-Type", "");
                        if (ct == null) ct = "";

                        if (!ct.startsWith("image/")) {
                            String body = response.body() != null ? response.body().string() : "";
                            runOnUiThread(() -> tvStatus.setText(body.isEmpty() ? "Success (non-image response)" : body));
                            return;
                        }

                        byte[] outBytes = response.body() != null ? response.body().bytes() : null;
                        if (outBytes == null || outBytes.length == 0) {
                            runOnUiThread(() -> tvStatus.setText("Empty image from server"));
                            return;
                        }

                        String name = "WM_" + System.currentTimeMillis();
                        Uri saved = saveToAlbum(outBytes, name);

                        runOnUiThread(() -> tvStatus.setText("Saved to WatermarkStudio"));
                    } catch (Exception e) {
                        runOnUiThread(() -> tvStatus.setText("Process failed: " + e.getMessage()));
                    } finally {
                        response.close();
                    }
                }
            });
        });
    }

    private Uri saveToAlbum(byte[] imageBytes, String displayNameNoExt) throws Exception {
        ContentValues values = new ContentValues();
        values.put(MediaStore.Images.Media.DISPLAY_NAME, displayNameNoExt + ".jpg");
        values.put(MediaStore.Images.Media.MIME_TYPE, "image/jpeg");

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            values.put(MediaStore.Images.Media.RELATIVE_PATH, ALBUM_RELATIVE_PATH);
            values.put(MediaStore.Images.Media.IS_PENDING, 1);
        }

        Uri uri = getContentResolver().insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values);
        if (uri == null) throw new Exception("MediaStore insert failed");

        try (OutputStream os = getContentResolver().openOutputStream(uri)) {
            if (os == null) throw new Exception("OpenOutputStream failed");
            os.write(imageBytes);
            os.flush();
        }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            values.clear();
            values.put(MediaStore.Images.Media.IS_PENDING, 0);
            getContentResolver().update(uri, values, null, null);
        }

        return uri;
    }

    private byte[] readBytes(Uri uri) throws Exception {
        try (InputStream is = getContentResolver().openInputStream(uri);
             ByteArrayOutputStream buffer = new ByteArrayOutputStream()) {

            if (is == null) throw new Exception("InputStream null");

            byte[] data = new byte[8192];
            int n;
            while ((n = is.read(data)) != -1) {
                buffer.write(data, 0, n);
            }
            return buffer.toByteArray();
        }
    }
}