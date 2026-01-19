package com.example.androidapp;

import android.location.Address;
import android.location.Geocoder;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.text.Editable;
import android.text.TextWatcher;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.TextView;
import android.widget.Toast;

import androidx.activity.ComponentActivity;
import androidx.exifinterface.media.ExifInterface;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.List;
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

    private static final String SERVER_UPLOAD_URL = "http://192.168.0.100:5000/upload";

    private ImageView imgPreview;
    private EditText etUsername;
    private Button btnUploadNow;
    private TextView tvStatus;
    private TextView tvCapturedTime;
    private TextView tvAddress;
    private TextView tvUsername;

    private Uri imageUri;

    private String capturedTimeText = "-";
    private String addressText = "No GPS info";

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
        tvAddress = findViewById(R.id.tvAddress);
        tvUsername = findViewById(R.id.tvUsername);

        imageUri = getIntent().getData();
        if (imageUri == null) {
            Toast.makeText(this, "No image selected", Toast.LENGTH_SHORT).show();
            finish();
            return;
        }

        imgPreview.setImageURI(imageUri);

        tvStatus.setText("");
        tvCapturedTime.setText("Time: -");
        tvAddress.setText("Address: -");
        tvUsername.setText("Username: " + getUsername());

        etUsername.addTextChangedListener(new TextWatcher() {
            @Override public void beforeTextChanged(CharSequence s, int start, int count, int after) {}
            @Override public void onTextChanged(CharSequence s, int start, int before, int count) {
                tvUsername.setText("Username: " + getUsername());
            }
            @Override public void afterTextChanged(Editable s) {}
        });

        loadMetadataAsync();

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

    private void loadMetadataAsync() {
        tvCapturedTime.setText("Time: Loading...");
        tvAddress.setText("Address: Loading...");

        bg.execute(() -> {
            String time = readExifTimeOrNow(imageUri);
            String addr = readExifAddress(imageUri);

            capturedTimeText = time;
            addressText = addr;

            runOnUiThread(() -> {
                tvCapturedTime.setText("Time: " + capturedTimeText);
                tvAddress.setText("Address: " + addressText);
                tvUsername.setText("Username: " + getUsername());
            });
        });
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

    private String readExifAddress(Uri uri) {
        try (InputStream is = getContentResolver().openInputStream(uri)) {
            if (is == null) return "Unknown";

            ExifInterface exif = new ExifInterface(is);
            float[] latLong = new float[2];
            boolean has = exif.getLatLong(latLong);
            if (!has) return "No GPS info";

            Geocoder geocoder = new Geocoder(this, Locale.getDefault());
            List<Address> list = geocoder.getFromLocation(latLong[0], latLong[1], 1);
            if (list != null && !list.isEmpty()) {
                String line = list.get(0).getAddressLine(0);
                if (line != null && !line.trim().isEmpty()) return line.trim();
            }
            return String.format(Locale.US, "Lat %.6f, Lng %.6f", latLong[0], latLong[1]);
        } catch (Exception e) {
            return "Unknown";
        }
    }

    private void uploadImage() {
        String username = getUsername();
        String device = String.format(Locale.US, "%s %s", Build.MANUFACTURER, Build.MODEL);
        long timestampMillis = System.currentTimeMillis();

        tvStatus.setText("Uploading...");

        byte[] imageBytes;
        try {
            imageBytes = readBytes(imageUri);
        } catch (Exception e) {
            tvStatus.setText("Failed to read image");
            return;
        }

        RequestBody fileBody = RequestBody.create(imageBytes, MediaType.parse("image/*"));

        MultipartBody requestBody = new MultipartBody.Builder()
                .setType(MultipartBody.FORM)
                .addFormDataPart("timestamp", String.valueOf(timestampMillis))
                .addFormDataPart("captured_time", capturedTimeText)
                .addFormDataPart("device", device)
                .addFormDataPart("username", username)
                .addFormDataPart("address", addressText)
                .addFormDataPart("image", "upload.jpg", fileBody)
                .build();

        Request request = new Request.Builder()
                .url(SERVER_UPLOAD_URL)
                .post(requestBody)
                .build();

        client.newCall(request).enqueue(new Callback() {
            @Override
            public void onFailure(Call call, java.io.IOException e) {
                runOnUiThread(() -> tvStatus.setText("Upload failed"));
            }

            @Override
            public void onResponse(Call call, Response response) {
                try {
                    if (!response.isSuccessful()) {
                        runOnUiThread(() -> tvStatus.setText("Server error"));
                        return;
                    }
                    runOnUiThread(() -> tvStatus.setText("Upload success"));
                } finally {
                    response.close();
                }
            }
        });
    }

    private byte[] readBytes(Uri uri) throws Exception {
        try (InputStream is = getContentResolver().openInputStream(uri);
             ByteArrayOutputStream buffer = new ByteArrayOutputStream()) {

            if (is == null) throw new Exception();

            byte[] data = new byte[8192];
            int n;
            while ((n = is.read(data)) != -1) {
                buffer.write(data, 0, n);
            }
            return buffer.toByteArray();
        }
    }
}
